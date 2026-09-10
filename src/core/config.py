"""Конфигурация приложения (env-driven)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки MCP-сервера справки по синтаксису 1С."""

    # Elasticsearch (внешний сервис в сети)
    elasticsearch_url: str = "http://192.168.31.31:9200"
    elasticsearch_index: str = "help1c_docs"
    elasticsearch_api_key: str = ""
    elasticsearch_timeout: int = 30
    elasticsearch_max_retries: int = 3

    # MCP server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

    # Данные
    hbk_path: str = "data/hbk/shcntx_ru.hbk"
    logs_directory: str = "logs"

    # Логирование
    log_level: str = "INFO"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
