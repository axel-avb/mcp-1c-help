"""Standalone-индексатор .hbk документации 1С в Elasticsearch.

Примеры:
    python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk
    python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk --reindex
"""

import argparse
import asyncio
import sys
from pathlib import Path

from src.core.config import settings
from src.core.elasticsearch import get_es_client
from src.parsers.hbk_parser import HBKParser
from src.parsers.indexer import ElasticsearchIndexer


async def run(hbk_path: Path, reindex: bool) -> int:
    if not hbk_path.exists():
        print(f"Файл не найден: {hbk_path}", file=sys.stderr)
        return 1

    es_client = get_es_client()
    if not await es_client.ensure_connected():
        print(f"Elasticsearch недоступен: {settings.elasticsearch_url}", file=sys.stderr)
        return 1

    if not reindex and await es_client.index_exists():
        count = await es_client.get_documents_count()
        if count > 0:
            print(
                f"Индекс '{es_client.index}' уже содержит {count} документов. "
                f"Используйте --reindex для перезаписи."
            )
            return 0

    print(f"Парсинг {hbk_path}...")
    parser = HBKParser()
    parsed = await asyncio.to_thread(parser.parse_file, str(hbk_path))

    if not parsed or not parsed.documentation:
        print("Не удалось распарсить документацию.", file=sys.stderr)
        return 1

    print(f"Найдено {len(parsed.documentation)} документов. Индексация...")

    def progress(indexed: int, total: int) -> None:
        if indexed % 1000 == 0 or indexed == total:
            print(f"  {indexed}/{total}")

    indexer = ElasticsearchIndexer(es_client)
    if reindex:
        success = await indexer.reindex_all(parsed, progress_callback=progress)
    else:
        success = await indexer.index_documentation(parsed, progress_callback=progress)

    if not success:
        print("Ошибка индексации.", file=sys.stderr)
        return 1

    count = await es_client.get_documents_count()
    print(f"Готово. Документов в индексе '{es_client.index}': {count}")
    await es_client.disconnect()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hbk",
        type=Path,
        default=Path(settings.hbk_path),
        help=f"Путь к .hbk файлу (по умолчанию: {settings.hbk_path})",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Удалить и пересоздать индекс (иначе индексация только если индекс пуст)",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.hbk, args.reindex))


if __name__ == "__main__":
    raise SystemExit(main())
