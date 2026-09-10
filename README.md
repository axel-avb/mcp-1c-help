# 1C Syntax Helper MCP (`mcp-1c-helper`)

Read-only MCP-сервер справки по синтаксису 1С:Предприятие 8.3. Ищет по индексу
документации в общем Elasticsearch и отдаёт результат ИИ-агентам через MCP.

Быстрый запуск — [QUICKSTART.md](QUICKSTART.md).

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
- Индекс задаётся в конфиге: `ELASTICSEARCH_INDEX` (по умолчанию `help1c_docs`).
  Индекс уже создан и наполнен; переиндексация — только вручную (см. ниже).
- MCP наружу публикуется на `8002`: `http://<host>:8002/mcp`.
- Логи пишутся в `/app/logs` (том `./logs`), уровень — `LOG_LEVEL`.

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
