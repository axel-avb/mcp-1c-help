"""Клиент Elasticsearch (внешний сервис)."""

from typing import Any, Dict, Optional

from elasticsearch import AsyncElasticsearch

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


INDEX_MAPPING: Dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "russian": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stop", "russian_stemmer"],
                }
            },
            "filter": {
                "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                "russian_stemmer": {"type": "stemmer", "language": "russian"},
            },
        },
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "type": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "russian",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "object": {"type": "keyword"},
            "syntax_ru": {"type": "text"},
            "syntax_en": {"type": "text"},
            "description": {"type": "text", "analyzer": "russian"},
            "parameters": {
                "type": "nested",
                "properties": {
                    "name": {"type": "text"},
                    "type": {"type": "keyword"},
                    "description": {"type": "text", "analyzer": "russian"},
                    "required": {"type": "boolean"},
                },
            },
            "return_type": {"type": "keyword"},
            "version_from": {"type": "keyword"},
            "examples": {"type": "text", "analyzer": "russian"},
            "source_file": {"type": "keyword"},
            "full_path": {"type": "keyword"},
        }
    },
}


class ElasticsearchClient:
    """Асинхронный клиент для работы с индексом документации 1С."""

    def __init__(self) -> None:
        self._client: Optional[AsyncElasticsearch] = None
        self._connected = False

    def _build(self) -> AsyncElasticsearch:
        kwargs: Dict[str, Any] = {
            "hosts": [settings.elasticsearch_url],
            "request_timeout": settings.elasticsearch_timeout,
            "max_retries": settings.elasticsearch_max_retries,
            "retry_on_timeout": True,
        }
        if settings.elasticsearch_api_key:
            kwargs["api_key"] = settings.elasticsearch_api_key
        return AsyncElasticsearch(**kwargs)

    async def ensure_connected(self) -> bool:
        """Устанавливает соединение при необходимости и проверяет доступность."""
        if self._client is None:
            self._client = self._build()
        try:
            await self._client.info()
            self._connected = True
        except Exception as exc:  # noqa: BLE001 - доступность backend не гарантируем
            logger.error(f"Не удалось подключиться к Elasticsearch: {exc}")
            self._connected = False
        return self._connected

    async def is_connected(self) -> bool:
        """Проверяет соединение с Elasticsearch."""
        if self._client is None:
            return await self.ensure_connected()
        try:
            return bool(await self._client.ping())
        except Exception:  # noqa: BLE001
            return False

    async def disconnect(self) -> None:
        """Закрывает соединение."""
        if self._client is not None:
            try:
                await self._client.close()
            finally:
                self._client = None
                self._connected = False

    @property
    def index(self) -> str:
        return settings.elasticsearch_index

    async def index_exists(self) -> bool:
        if self._client is None:
            return False
        return bool(await self._client.indices.exists(index=self.index))

    async def create_index(self) -> bool:
        if self._client is None:
            return False
        await self._client.indices.create(index=self.index, body=INDEX_MAPPING)
        logger.info(f"Индекс '{self.index}' создан")
        return True

    async def delete_index(self) -> bool:
        if self._client is not None and await self.index_exists():
            await self._client.indices.delete(index=self.index)
            return True
        return False

    async def get_documents_count(self) -> int:
        if self._client is None:
            return 0
        response = await self._client.count(index=self.index)
        return int(response["count"])

    async def refresh_index(self) -> bool:
        if self._client is None:
            return False
        await self._client.indices.refresh(index=self.index)
        return True

    async def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Elasticsearch недоступен")
        return await self._client.search(index=self.index, body=query)

    async def bulk(self, body: list) -> Dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Elasticsearch недоступен")
        return await self._client.bulk(body=body)


_client: Optional[ElasticsearchClient] = None


def get_es_client() -> ElasticsearchClient:
    """Возвращает singleton-клиент Elasticsearch."""
    global _client
    if _client is None:
        _client = ElasticsearchClient()
    return _client
