# 1C Syntax Helper MCP (`mcp-1c-helper`)

Read-only MCP-сервер справки по синтаксису 1С:Предприятие 8.3. Ищет по индексу
документации в общем Elasticsearch и отдаёт результат ИИ-агентам через MCP.

- Краткий запуск — [QUICKSTART.md](QUICKSTART.md).
- Полный пошаговый мануал по Docker — [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Состав

```
src/
  server.py          FastMCP, 5 tools, streamable-http
  formatting.py      форматирование текстовых ответов
  search/            построение и ранжирование запросов
  parsers/           парсер .hbk + индексатор в Elasticsearch
  models/            pydantic-модели документации
  core/              конфиг, клиент ES, логирование, утилиты
scripts/
  index_hbk.py       standalone-индексатор .hbk
tests/               parser / search / ES
data/
  hbk/               сюда кладётся .hbk для индексации
compose.yml          один сервис + внешний ES
```

## Окружение

- Elasticsearch: внешний сервис в сети — `ELASTICSEARCH_URL`
  (по умолчанию `http://192.168.31.31:9200`).
- Индекс задаётся в конфиге: `ELASTICSEARCH_INDEX` (по умолчанию `help1c_docs_v2`,
  семантический; `help1c_docs` — прежний лексический).
- Эмбеддинги: внешний сервис `EMBEDDING_URL` (`http://192.168.31.32:8081/v1`).
  Если пусто — поиск только лексический (BM25).
- MCP наружу публикуется на `8002`: `http://<host>:8002/mcp`.
- Логи пишутся в `/app/logs` (том `./logs`), уровень — `LOG_LEVEL`.

## Поиск

- `find_1c_help` работает гибридно: BM25 + kNN по эмбеддингам, слияние через RRF.
- Остальные tools — по точному имени/объекту, лексический поиск.
- Eval качества (description-запросы): `python -m scripts.eval_search`.
  Ориентир на индексе `help1c_docs_v2`: Recall@3 ≈ 46%, Recall@5 ≈ 50%.

## Запуск

```bash
cp .env.example .env      # при необходимости поправить URL/индекс
docker compose up -d --build
```

Проверка:

```bash
curl -s -X POST http://localhost:8002/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## MCP tools

- `find_1c_help(query, limit=10)` — поиск по имени, описанию или ключевым словам.
- `get_quick_reference(element_name, object_name?)` — краткий синтаксис и описание.
- `get_syntax_info(element_name, object_name?, include_examples=true)` — полная справка.
- `list_object_members(object_name, member_type="all", limit=50)` — методы/свойства/события объекта.
- `search_by_context(query, context, object_name?, limit=10)` — поиск с фильтром `global|object|all`.

## Индексация `.hbk`

Автоиндексации при старте нет — индекс наполняется вручную.

```bash
# в контейнере (использует .env)
docker compose run --rm mcp-server python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk --reindex

# локально
pip install -r requirements.txt
python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk --reindex
```

Без `--reindex` индексация выполняется только если индекс пуст. Для извлечения
`.hbk` нужен `7z` (в образе ставится `p7zip-full`).

## Семантический индекс (эмбеддинги)

Отдельный скрипт читает готовый индекс, считает векторы через `EMBEDDING_URL` и
пишет в новый индекс с полем `embedding`. Исходный индекс не меняется.

```bash
docker run --rm \
  -e ELASTICSEARCH_URL=http://192.168.31.31:9200 \
  -e EMBEDDING_URL=http://192.168.31.32:8081/v1 \
  mcp-1c-helper:local \
  python -m scripts.build_semantic_index \
    --source help1c_docs --target help1c_docs_v2 --recreate
```

После сборки укажи `ELASTICSEARCH_INDEX=help1c_docs_v2` в `.env` — `find_1c_help`
включит kNN+RRF автоматически (при заданном `EMBEDDING_URL`).

## Подключение opencode

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

## Разработка

```bash
pip install -r requirements-dev.txt
python -m src.server                 # запуск FastMCP локально
python -m pytest tests/ -m unit      # unit тесты
```
