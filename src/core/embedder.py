"""Клиент внешнего сервиса эмбеддингов (OpenAI-совместимый)."""

import httpx

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingError(RuntimeError):
    """Ошибка сервиса эмбеддингов."""


def enabled() -> bool:
    """Включены ли эмбеддинги (задан EMBEDDING_URL)."""
    return bool(settings.embedding_url)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Считает векторы для списка текстов одним запросом."""
    if not texts:
        return []
    if not enabled():
        raise EmbeddingError("EMBEDDING_URL не задан")

    url = f"{settings.embedding_url.rstrip('/')}/embeddings"
    headers = {"Content-Type": "application/json"}
    if settings.embedding_key:
        headers["Authorization"] = f"Bearer {settings.embedding_key}"

    payload = {"model": settings.embedding_model, "input": texts}
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()["data"]

    vectors = [item["embedding"] for item in data]
    if len(vectors) != len(texts):
        raise EmbeddingError(
            f"Ожидалось {len(texts)} векторов, получено {len(vectors)}"
        )
    return vectors


async def embed_query(query: str) -> list[float]:
    """Считает вектор для поискового запроса."""
    vectors = await embed_texts([query])
    return vectors[0]
