"""Сборка единого индекса из всех корпусов .hbk.

Корпуса:
    shcntx_ru.hbk -> context   (контекстная справка: объекты/методы/свойства)
    shquery_ru.hbk -> query    (язык запросов)
    shclang_ru.hbk -> devguide (руководство/встроенный язык)
    shlang_ru.hbk -> language  (конструкции языка, типы, директивы)

Примеры:
    python -m scripts.index_collections --hbk-dir data/hbk --index help1c_docs_v3 --recreate
    python -m scripts.index_collections --hbk-dir data/hbk --only query,language
"""

import argparse
import asyncio
import sys
from pathlib import Path

from src.core.config import settings
from src.core.elasticsearch import get_es_client
from src.models.doc_models import Documentation
from src.parsers.hbk_parser import HBKParser
from src.parsers.indexer import ElasticsearchIndexer
from src.parsers.plain_parser import PlainParser

COLLECTIONS = [
    ("shcntx_ru.hbk", "context", "context"),
    ("shquery_ru.hbk", "query", "plain"),
    ("shclang_ru.hbk", "devguide", "plain"),
    ("shlang_ru.hbk", "language", "plain"),
]


def collect_documents(hbk_dir: Path, sources: set[str]) -> list[Documentation]:
    documents: list[Documentation] = []
    for filename, source, kind in COLLECTIONS:
        if source not in sources:
            continue
        path = hbk_dir / filename
        if not path.exists():
            print(f"  [{source}] пропуск: нет файла {path}", file=sys.stderr)
            continue

        if kind == "context":
            parsed = HBKParser().parse_file(str(path))
            docs = parsed.documentation if parsed else []
            for doc in docs:
                doc.source = source
        else:
            docs = PlainParser(source).parse_file(str(path))

        print(f"  [{source}] {filename}: {len(docs)} документов")
        documents.extend(docs)
    return documents


async def run(hbk_dir: Path, index: str, recreate: bool, sources: set[str]) -> int:
    settings.elasticsearch_index = index

    es = get_es_client()
    if not await es.ensure_connected():
        print(f"Elasticsearch недоступен: {settings.elasticsearch_url}", file=sys.stderr)
        return 1

    print(f"Сбор документов из {hbk_dir}...")
    documents = collect_documents(hbk_dir, sources)
    if not documents:
        print("Не собрано ни одного документа.", file=sys.stderr)
        return 1
    print(f"Всего документов: {len(documents)}")

    def progress(indexed: int, total: int) -> None:
        if indexed % 2000 == 0 or indexed == total:
            print(f"  {indexed}/{total}")

    indexer = ElasticsearchIndexer(es)
    if recreate:
        ok = await indexer.reindex_documents(documents, progress_callback=progress)
    else:
        ok = await indexer.index_documents(documents, progress_callback=progress)

    if not ok:
        print("Ошибка индексации.", file=sys.stderr)
        return 1

    count = await es.get_documents_count(index)
    print(f"Готово. Документов в '{index}': {count}")
    await es.disconnect()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    hbk_default = Path(settings.hbk_path)
    if not hbk_default.is_dir():
        hbk_default = hbk_default.parent
    parser.add_argument("--hbk-dir", type=Path, default=hbk_default)
    parser.add_argument("--index", default="help1c_docs_v4")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument(
        "--only",
        default="context,query,devguide,language",
        help="Список корпусов через запятую",
    )
    args = parser.parse_args()
    sources = {s.strip() for s in args.only.split(",") if s.strip()}
    return asyncio.run(run(args.hbk_dir, args.index, args.recreate, sources))


if __name__ == "__main__":
    raise SystemExit(main())
