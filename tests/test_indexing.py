"""Тест 3: Полная индексация документации в Elasticsearch."""

import asyncio
import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.elasticsearch import get_es_client
from src.parsers.hbk_parser import HBKParser
from src.parsers.indexer import ElasticsearchIndexer


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.elasticsearch
@pytest.mark.indexer
@pytest.mark.asyncio
async def test_indexing():
    """Тест индексации документации."""
    print("=== Тест 3: Индексация в Elasticsearch ===")
    es_client = get_es_client()

    try:
        # Подключаемся к Elasticsearch
        connected = await es_client.ensure_connected()
        if not connected:
            print("❌ Elasticsearch недоступен")
            return False
        
        # Создаем индексатор с передачей es_client
        indexer = ElasticsearchIndexer(es_client)
        
        # Парсим .hbk файл
        hbk_dir = Path(settings.hbk_path).parent
        hbk_files = list(hbk_dir.glob("*.hbk"))
        
        if not hbk_files:
            print("❌ .hbk файл не найден")
            return False
        
        parser = HBKParser(max_files_per_type=3, max_total_files=50)
        parsed_hbk = parser.parse_file(str(hbk_files[0]))
        
        if not parsed_hbk or not parsed_hbk.documentation:
            print("❌ Нет данных для индексации")
            return False
        
        print(f"📚 Готово к индексации: {len(parsed_hbk.documentation)} документов")
        
        # Запускаем индексацию
        start_time = time.time()
        success = await indexer.reindex_all(parsed_hbk)
        index_time = time.time() - start_time
        
        if success:
            docs_count = await es_client.get_documents_count()
            print(f"✅ Индексация завершена успешно:")
            print(f"   • Время: {index_time:.2f} сек")
            print(f"   • Документов в индексе: {docs_count}")
            
            # Проверка критерия производительности
            if index_time < 120:
                print("✅ Критерий < 2 минут выполнен")
            else:
                print("⚠️ Индексация заняла > 2 минут")
                
            return True
        else:
            print("❌ Ошибка индексации")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        await es_client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_indexing())
