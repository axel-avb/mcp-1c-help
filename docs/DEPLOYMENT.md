# Развёртывание `mcp-1c-helper` в Docker — пошаговый мануал

Документ рассчитан на развёртывание в прод «с нуля» и на обновление уже
запущенного сервиса. Все команды выполняются на хосте, где будет стоять контейнер.

---

## 1. Что разворачивается

- **Один контейнер** `mcp-1c-helper` — MCP-сервер (FastMCP, streamable-http).
- Слушает `8000` внутри контейнера, наружу публикуется на **`8002`**.
- 5 tools: `find_1c_help`, `get_syntax_info`, `get_quick_reference`,
  `search_by_context`, `list_object_members`.
- **Внешние зависимости** (в контейнер не входят, должны быть доступны по сети):
  - Elasticsearch — `ELASTICSEARCH_URL` (по умолчанию `http://192.168.31.31:9200`);
  - сервис эмбеддингов — `EMBEDDING_URL` (по умолчанию `http://192.168.31.32:8081/v1`).
- Индексы в Elasticsearch:
  - **`help1c_docs_v2`** — рабочий (документы + векторы, семантический поиск);
  - `help1c_docs` — прежний лексический (только BM25), остаётся как источник для пересборки v2.

---

## 2. Требования

| Что | Версия / значение |
|---|---|
| Docker Engine | 20+ |
| Docker Compose | v2 (`docker compose version`) |
| ОС | Linux (amd64/arm64) |
| RAM | ~0.5–1 ГБ на контейнер |
| Порты | свободен TCP **8002** |
| Сеть до ES | `curl http://192.168.31.31:9200/_cluster/health` с хоста |
| Сеть до эмбеддера | `curl http://192.168.31.32:8081/v1/models` с хоста |

Индексация при старте **не запускается** — сервер только читает готовый индекс.

---

## 3. Получить код

```bash
git clone https://github.com/axel-avb/mcp-1c-help.git
cd mcp-1c-help
mkdir -p data/hbk logs
```

`data/hbk` — папка для `.hbk` (если понадобится пересборка), `logs` — файлы логов.
Обе монтируются в контейнер. Файл с учётными данными (`.git_creditionals.md`) в
репозиторий не входит и игнорируется.

---

## 4. Конфигурация `.env`

```bash
cp .env.example .env
```

Проверь значения (для текущего окружения они уже верные):

| Переменная | Значение для прода | Смысл |
|---|---|---|
| `ELASTICSEARCH_URL` | `http://192.168.31.31:9200` | адрес общего Elasticsearch |
| `ELASTICSEARCH_INDEX` | `help1c_docs_v2` | рабочий семантический индекс |
| `ELASTICSEARCH_API_KEY` | пусто | ключ, если ES с авторизацией |
| `ELASTICSEARCH_TIMEOUT` | `30` | таймаут запроса, сек |
| `ELASTICSEARCH_MAX_RETRIES` | `3` | повторы на транспортном уровне клиента |
| `MCP_HOST` | `0.0.0.0` | адрес прослушивания |
| `MCP_PORT` | `8000` | порт **внутри** контейнера (наружу 8002) |
| `EMBEDDING_URL` | `http://192.168.31.32:8081/v1` | эмбеддер; **пусто = только лексика** |
| `EMBEDDING_MODEL` | `jina-code-embeddings-1.5b-GGUF` | имя модели |
| `EMBEDDING_KEY` | пусто | bearer-ключ, если нужен |
| `EMBEDDING_DIMS` | `1536` | размерность вектора (должна совпасть с индексом!) |
| `HBK_PATH` | `data/hbk/shcntx_ru.hbk` | путь к `.hbk` для скрипта индексации |
| `LOG_LEVEL` | `INFO` | уровень логов |
| `LOGS_DIRECTORY` | `logs` | каталог логов внутри контейнера |
| `DEBUG` | `false` | подробный формат логов |

> Если хочешь временно **без семантики** — оставь `EMBEDDING_URL=` пустым
> (сервер сам перейдёт на BM25). Если сменишь `EMBEDDING_DIMS` или модель —
> индекс нужно пересобрать (шаг 8).

---

## 5. Освободить порт 8002 (важно)

Сейчас на `8002` может работать **старая** версия сервиса. Новый контейнер с тем же
портом не поднимется. Найди и останови старый:

```bash
# найти, кто занимает 8002
docker ps --filter "publish=8002"

# остановить (подставь имя/ID из вывода)
docker rm -f <old-container-name>
```

Если старый сервис управлялся другим compose-проектом — останови его там
(`docker compose down` в его каталоге). Имя нового контейнера — `mcp-1c-helper`;
если такое имя уже занято, тоже удали старый: `docker rm -f mcp-1c-helper`.

---

## 6. Сборка и запуск

```bash
docker compose build
docker compose up -d
docker compose ps
```

Ждём статус `Up ... (healthy)`. Смотрим логи:

```bash
docker compose logs -f mcp-server
```

В логах должно быть `Starting MCP server '1c-syntax-helper' with transport
'streamable-http' on http://0.0.0.0:8000/mcp`.

---

## 7. Проверка работоспособности

### 7.1. Tools (через MCP-клиент)

`tools/list` у FastMCP требует рукопожатия, поэтому голый `curl` не подходит —
используем встроенный клиент:

```bash
docker compose exec mcp-server python -c "
import asyncio
from fastmcp import Client
async def main():
    async with Client('http://127.0.0.1:8000/mcp') as c:
        print([t.name for t in await c.list_tools()])
asyncio.run(main())
"
```

Ожидаемо: `['find_1c_help', 'get_syntax_info', 'get_quick_reference', 'search_by_context', 'list_object_members']`.

### 7.2. Живой поиск

```bash
docker compose exec mcp-server python -c "
import asyncio
from fastmcp import Client
async def main():
    async with Client('http://127.0.0.1:8000/mcp') as c:
        r = await c.call_tool('find_1c_help', {'query': 'округлить число', 'limit': 3})
        print(r.content[0].text)
asyncio.run(main())
"
```

Если индекс и эмбеддер доступны — вернётся список элементов справки.

---

## 8. Индексы

### 8.1. Текущее состояние

В общем Elasticsearch уже есть **`help1c_docs_v2`** (24 683 документа с векторами).
Если он на месте — пересборка не нужна, сервер сразу готов к работе.

Проверить:

```bash
curl -s http://192.168.31.31:9200/_cat/indices/help1c_docs*?v
```

### 8.2. Пересобрать v2 из лексического индекса (рекомендуется)

Берёт готовый `help1c_docs`, считает векторы через `EMBEDDING_URL` и пишет в
`help1c_docs_v2`. Исходный индекс не изменяется. Занимает ~15 минут.

```bash
docker compose run --rm mcp-server \
  python -m scripts.build_semantic_index \
    --source help1c_docs --target help1c_docs_v2 --recreate
```

### 8.3. Полная пересборка из `.hbk`

Если лексического индекса тоже нет (совсем с нуля):

```bash
# 1) положить архив документации
cp /path/to/shcntx_ru.hbk data/hbk/shcntx_ru.hbk

# 2) собрать сразу семантический индекс v2 из .hbk
#    (ELASTICSEARCH_INDEX в .env = help1c_docs_v2, EMBEDDING_URL задан)
docker compose run --rm mcp-server \
  python -m scripts.index_hbk --hbk data/hbk/shcntx_ru.hbk --reindex
```

Без `--reindex` индексация выполняется только если индекс пуст. Для разбора `.hbk`
в образе уже стоит `p7zip`.

### 8.4. Проверка качества (eval)

```bash
docker compose run --rm mcp-server python -m scripts.eval_search
```

Ориентир на `help1c_docs_v2`: `Recall@3 ≈ 46%`, `Recall@5 ≈ 50%`.

---

## 9. Подключение в opencode

Добавь в конфиг среды (`.opencode/opencode.json` или `opencode.jsonc`):

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

После подключения инструменты появятся как `mcp-1c-helper_find_1c_help` и т.д.

---

## 10. Эксплуатация

| Действие | Команда |
|---|---|
| Логи в реальном времени | `docker compose logs -f mcp-server` |
| Логи в файлах | `./logs/app.log`, `./logs/errors.log` |
| Рестарт | `docker compose restart mcp-server` |
| Обновление кода | `git pull && docker compose up -d --build` |
| Остановить | `docker compose down` |
| Статус/hhealth | `docker compose ps` |
| Зайти в контейнер | `docker compose exec mcp-server sh` |

`docker compose down` не удаляет `./data` и `./logs` — они на хосте.

---

## 11. Устранение проблем

**Контейнер не стартует, `port is already allocated`.**
Порт 8002 занят (шаг 5). Либо освободи, либо смени маппинг в `compose.yml`
(`"8002:8000"` → `"8003:8000"`) и URL в opencode.

**`Elasticsearch недоступен` в логах / пустые ответы.**
Проверь доступность ES **из контейнера**:
```bash
docker compose exec mcp-server python -c "import urllib.request;print(urllib.request.urlopen('http://192.168.31.31:9200/_cluster/health',timeout=5).read())"
```
Убедись, что `ELASTICSEARCH_URL` и `ELASTICSEARCH_INDEX` в `.env` верные.

**Семантика не работает, в логах `Векторный поиск недоступен, только BM25`.**
Значит, эмбеддер недоступен или в индексе нет векторов. Проверь:
```bash
curl -s http://192.168.31.32:8081/v1/models
```
и что `ELASTICSEARCH_INDEX=help1c_docs_v2`. Сервер при этом продолжает работать
на BM25.

**Индекс не найден / мало документов.**
```bash
curl -s http://192.168.31.31:9200/help1c_docs_v2/_count
```
Если пусто — пересобери (шаг 8.2/8.3).

**Контейнер `unhealthy`.**
```bash
docker compose logs mcp-server | tail -50
```
Частые причины — ES/эмбеддер недоступны или неверный `.env`.

**Нет прав на `./data`/`./logs`.**
Docker мог создать их от root. Поправь владельца: `sudo chown -R $(id -u):$(id -g) data logs`.

---

## 12. Откат на лексический режим

Нужен только BM25 (например, эмбеддер лёг и не должен тормозить):

```bash
# в .env
ELASTICSEARCH_INDEX=help1c_docs
EMBEDDING_URL=

docker compose up -d
```

---

## Приложение A. Структура

```
src/server.py            FastMCP, 5 tools, streamable-http
src/formatting.py        форматирование ответов
src/search/              построение запросов, BM25+kNN, RRF, ранкер
src/parsers/             парсер .hbk + индексатор (с эмбеддингами)
src/core/                конфиг, клиент ES, эмбеддер, логи, утилиты
scripts/index_hbk.py            индексация .hbk в ES
scripts/build_semantic_index.py миграция индекса + расчёт векторов
scripts/eval_search.py          замер качества поиска
compose.yml              один сервис, внешние ES/эмбеддер
```

## Приложение B. Шпаргалка команд

```bash
cp .env.example .env
mkdir -p data/hbk logs
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f mcp-server
# проверка tools — см. шаг 7.1
docker compose run --rm mcp-server python -m scripts.build_semantic_index --source help1c_docs --target help1c_docs_v2 --recreate
docker compose run --rm mcp-server python -m scripts.eval_search
docker compose down
```
