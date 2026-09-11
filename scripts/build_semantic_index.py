"""Миграция индекса с расчётом эмбеддингов.

Читает документы из исходного индекса, считает векторы через внешний
эмбеддер и пишет в новый индекс (с полем `embedding`). Исходный не меняется.

Примеры:
    python -m scripts.build_semantic_index
    python -m scripts.build_semantic_index --source help1c_docs --target help1c_docs_v2 --recreate
"""

import argparse
import asyncio
import sys

from src.core import embedder
from src.core.config import settings
from src.core.elasticsearch import get_es_client
from src.core.logging import get_logger
from src.parsers.indexer import embedding_text

logger = get_logger(__name__)


def _flush(batch: list[dict]) -> list:
    body = []
    for doc in batch:
        body.append({"index": {"_index": _TARGET, "_id": doc["id"]}})
        body.append(doc)
    return body


_TARGET = ""


async def run(source: str, target: str, batch_size: int, recreate: bool) -> int:
    global _TARGET
    _TARGET = target

    if not embedder.enabled():
        print("EMBEDDING_URL не задан", file=sys.stderr)
        return 1

    es = get_es_client()
    if not await es.ensure_connected():
        print(f"Elasticsearch недоступен: {settings.elasticsearch_url}", file=sys.stderr)
        return 1

    if await es.index_exists(source):
        total_source = await es.get_documents_count(source)
    else:
        print(f"Исходный индекс не найден: {source}", file=sys.stderr)
        return 1

    if await es.index_exists(target):
        if not recreate:
            print(f"Целевой индекс уже существует: {target} (используйте --recreate)", file=sys.stderr)
            return 1
        await es.delete_index(target)
    await es.create_index(target)

    print(f"Источник: {source} ({total_source} док.) -> цель: {target}, батч {batch_size}")

    batch: list[dict] = []
    processed = 0
    indexed = 0

    async for hit in es.scan_all(source):
        doc = dict(hit.get("_source", {}))
        doc["id"] = hit.get("_id", doc.get("id"))
        batch.append(doc)
        processed += 1

        if len(batch) >= batch_size:
            indexed += await _index_batch(es, batch)
            print(f"  {processed}/{total_source} обработано, {indexed} проиндексировано")
            batch = []

    if batch:
        indexed += await _index_batch(es, batch)

    await es.refresh_index(target)
    count = await es.get_documents_count(target)
    print(f"Готово. Документов в '{target}': {count}")
    if count != total_source:
        print(f"ВНИМАНИЕ: было {total_source}, стало {count}", file=sys.stderr)
    await es.disconnect()
    return 0


async def _index_batch(es, batch: list[dict]) -> int:
    vectors = await embedder.embed_texts([embedding_text(doc) for doc in batch])
    for doc, vector in zip(batch, vectors):
        doc["embedding"] = vector
    response = await es.bulk(_flush(batch))
    if response.get("errors"):
        errors = [i for i in response.get("items", []) if i.get("index", {}).get("status", 200) >= 300]
        print(f"Ошибки bulk: {len(errors)}", file=sys.stderr)
    return len(batch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="help1c_docs")
    parser.add_argument("--target", default="help1c_docs_v2")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size должен быть положительным")
    return asyncio.run(run(args.source, args.target, args.batch_size, args.recreate))


if __name__ == "__main__":
    raise SystemExit(main())
