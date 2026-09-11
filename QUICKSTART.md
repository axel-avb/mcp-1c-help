# QUICKSTART — `mcp-1c-helper`

Краткий запуск MCP-сервера справки по синтаксису 1С.

## Требования

- Docker + Docker Compose.
- Доступ к общему Elasticsearch: `http://192.168.31.31:9200` (индекс `help1c_docs` уже создан).
- Свободный порт `8002` на хосте.

## Запуск за 4 шага

```bash
# 1. Конфиг (при необходимости поправить URL/индекс)
cp .env.example .env

# 2. Сборка и запуск
docker compose up -d --build

# 3. Проверка, что контейнер поднялся
docker compose ps
```

```bash
# 4. Проверка MCP: должен вернуться список из 5 tools
curl -s -X POST http://localhost:8002/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Подключение в opencode

```json
{
  "mcp": {
    "mcp-1c-helper": {
      "type": "remote",
      "url": "http://192.168.31.31:8002/mcp",
      "enabled": true
    }
  }
}
```

## Индексация `.hbk`

Автоиндексации при старте нет. Индекс `help1c_docs` уже наполнен; переиндексация —
только вручную. Нужен `7z` (в образе ставится `p7zip-full`).

```bash
# переиндексация (удаляет и пересоздаёт индекс)
docker compose run --rm mcp-server \
  python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk --reindex

# без --reindex: индексирует только если индекс пуст
docker compose run --rm mcp-server \
  python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk
```

Положить `.hbk` перед запуском: `data/hbk/shcntx_ru.hbk`.

## Семантический поиск (эмбеддинги)

По умолчанию `.env` уже указывает на `help1c_docs_v2` и эмбеддер
(`EMBEDDING_URL=http://192.168.31.32:8081/v1`). Индекс `help1c_docs_v2` уже собран.

Пересобрать его из лексического `help1c_docs` (например, после смены модели):

```bash
docker run --rm \
  -e ELASTICSEARCH_URL=http://192.168.31.31:9200 \
  -e EMBEDDING_URL=http://192.168.31.32:8081/v1 \
  mcp-1c-helper:local \
  python -m scripts.build_semantic_index \
    --source help1c_docs --target help1c_docs_v2 --recreate
```

Проверить качество: `python -m scripts.eval_search`
(в контейнере — `docker run --rm ... python -m scripts.eval_search`).

## Если не работает

- **`Elasticsearch недоступен`** — проверь `ELASTICSEARCH_URL` в `.env` и доступность
  `curl http://192.168.31.31:9200/_cluster/health`.
- **Индекс пустой** — выполни переиндексацию с `--reindex` (см. выше).
- **Порт занят** (`address already in use`) — поменяй маппинг в `compose.yml`
  (`"8002:8000"` → другой свободный порт).
- **Контейнер unhealthy** — `docker compose logs mcp-server`.
