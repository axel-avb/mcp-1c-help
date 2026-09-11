"""Индексатор документации в Elasticsearch."""

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from src.models.doc_models import Documentation, ParsedHBK
from src.core import embedder
from src.core.elasticsearch import ElasticsearchClient
from src.core.logging import get_logger

logger = get_logger(__name__)


def embedding_text(doc: Dict[str, Any]) -> str:
    """Текст документа для эмбеддинга (с контекстом объекта)."""
    parts = [
        doc.get("full_path") or doc.get("name", ""),
        doc.get("syntax_ru", ""),
        doc.get("description", ""),
    ]
    return ". ".join(part for part in parts if part)[:4000]


class ElasticsearchIndexer:
    """Индексатор документации в Elasticsearch."""
    
    def __init__(self, es_client: ElasticsearchClient):
        self.es_client = es_client
        self.batch_size = 100
        self.max_retries = 3
    
    async def index_documentation(
        self, 
        parsed_hbk: ParsedHBK,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Индексирует документацию из ParsedHBK в Elasticsearch.
        
        Args:
            parsed_hbk: Распарсенные данные HBK
            progress_callback: Callback для отчёта о прогрессе (indexed, total)
        
        Returns:
            bool: True если успешно, False иначе
        """
        if not await self.es_client.is_connected():
            logger.error("Нет подключения к Elasticsearch")
            return False
        
        try:
            # Проверяем/создаем индекс
            if not await self.es_client.index_exists():
                logger.info("Создаем индекс Elasticsearch")
                await self.es_client.create_index()
            
            # Индексируем документы батчами с отчётом о прогрессе
            total_docs = len(parsed_hbk.documentation)
            indexed_count = 0
            
            for i in range(0, total_docs, self.batch_size):
                batch = parsed_hbk.documentation[i:i + self.batch_size]
                
                success = await self._index_batch(batch)
                if success:
                    indexed_count += len(batch)
                    
                    # Вызываем callback для отчёта о прогрессе
                    if progress_callback:
                        progress_callback(indexed_count, total_docs)
                else:
                    logger.error(f"Ошибка индексации батча {i}-{i+len(batch)}")
            
            # Принудительно обновляем индекс для немедленного отражения изменений
            await self.es_client.refresh_index()
            
            return indexed_count == total_docs
            
        except Exception as e:
            logger.error(f"Ошибка индексации документации: {e}")
            return False
    
    async def _index_batch(self, documents: List[Documentation]) -> bool:
        """Индексирует батч документов."""
        if not documents:
            return True
        
        try:
            payloads = [self._prepare_document(doc) for doc in documents]

            if embedder.enabled():
                vectors = await embedder.embed_texts(
                    [embedding_text(payload) for payload in payloads]
                )
                for payload, vector in zip(payloads, vectors):
                    payload["embedding"] = vector

            # Подготавливаем bulk запрос
            bulk_body = []

            for doc, payload in zip(documents, payloads):
                bulk_body.append({
                    "index": {
                        "_index": self.es_client.index,
                        "_id": doc.id
                    }
                })
                bulk_body.append(payload)

            response = await self.es_client.bulk(bulk_body)

            if response.get("errors"):
                logger.warning("Есть ошибки в bulk запросе")
                for item in response.get("items", []):
                    if "index" in item and "error" in item["index"]:
                        logger.error(f"Ошибка индексации документа: {item['index']['error']}")

            return not response.get("errors", True)
            
        except Exception as e:
            logger.error(f"Ошибка выполнения bulk запроса: {e}")
            return False
    
    def _prepare_document(self, doc: Documentation) -> Dict[str, Any]:
        """Подготавливает документ для индексации в Elasticsearch."""
        es_doc = {
            "id": doc.id,
            "type": doc.type.value,
            "name": doc.name,
            "object": doc.object,
            "syntax_ru": doc.syntax_ru,
            "syntax_en": doc.syntax_en,
            "description": doc.description,
            "parameters": [
                {
                    "name": param.name,
                    "type": param.type,
                    "description": param.description,
                    "required": param.required
                }
                for param in doc.parameters
            ],
            "return_type": doc.return_type,
            "version_from": doc.version_from,
            "examples": doc.examples,
            "source_file": doc.source_file,
            "full_path": doc.full_path,
            "indexed_at": datetime.now().isoformat()
        }
        
        return es_doc
    
    async def reindex_all(
        self, 
        parsed_hbk: ParsedHBK,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Переиндексирует всю документацию (удаляет старый индекс и создает новый).
        
        Args:
            parsed_hbk: Распарсенные данные HBK
            progress_callback: Callback для отчёта о прогрессе (indexed, total)
        
        Returns:
            bool: True если успешно, False иначе
        """
        try:
            await self.es_client.delete_index()
            await self.es_client.create_index()
            return await self.index_documentation(parsed_hbk, progress_callback)

        except Exception as e:
            logger.error(f"Ошибка переиндексации: {e}")
            return False
