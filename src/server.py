"""FastMCP-сервер справки по синтаксису 1С.

Read-only MCP-обёртка над индексом документации в Elasticsearch.
"""

import os
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from src import formatting
from src.core.config import settings
from src.core.elasticsearch import get_es_client
from src.search.search_service import SearchService

mcp = FastMCP("1c-syntax-helper")


def _service() -> SearchService:
    return SearchService(get_es_client())


@mcp.tool()
async def find_1c_help(
    query: Annotated[
        str,
        Field(description='Поисковая строка на русском, напр. "СтрДлина", "количество символов в строке".'),
    ],
    limit: Annotated[
        int,
        Field(description="Сколько результатов вернуть (1..50). По умолчанию 10."),
    ] = 10,
) -> str:
    """Найти элементы в справке 1С по имени ИЛИ по описанию, если точное имя неизвестно.

    ИСПОЛЬЗУЙ, когда не знаешь точное имя элемента или ищешь по словам/смыслу.
    НЕ ИСПОЛЬЗУЙ, если точное имя уже известно — тогда get_syntax_info или get_quick_reference.

    Пример: find_1c_help(query="количество символов в строке", limit=5)
    Возвращает: нумерованный список найденных элементов с кратким описанием.
    """
    results = await _service().find_help_by_query(query, limit)
    if results.get("error"):
        return f"Ошибка поиска: {results['error']}"
    if not results.get("results"):
        return formatting.not_found(query)
    return formatting.search_results(results["results"], query)


@mcp.tool()
async def get_syntax_info(
    element_name: Annotated[
        str,
        Field(description='Точное имя элемента, напр. "СтрДлина", "Добавить".'),
    ],
    object_name: Annotated[
        str | None,
        Field(description='Имя объекта для методов/свойств, напр. "ТаблицаЗначений". Необязательно.'),
    ] = None,
    include_examples: Annotated[
        bool,
        Field(description="true — добавить примеры кода (по умолчанию true)."),
    ] = True,
) -> str:
    """Полная справка по элементу с ТОЧНЫМ именем: синтаксис, параметры, возвращаемое значение, примеры.

    ИСПОЛЬЗУЙ, когда имя элемента известно точно.
    Для метода или свойства объекта обязательно укажи object_name.
    НЕ ИСПОЛЬЗУЙ для поиска по описанию — сначала вызови find_1c_help.

    Пример: get_syntax_info(element_name="Добавить", object_name="ТаблицаЗначений")
    """
    result = await _service().get_detailed_syntax_info(
        element_name, object_name, include_examples
    )
    if not result:
        context = f" объекта '{object_name}'" if object_name else ""
        return formatting.not_found(f"Элемент '{element_name}'{context}")

    text = formatting.syntax_info(result)
    if include_examples and result.get("examples"):
        examples = result["examples"]
        if isinstance(examples, list) and examples:
            text += "💡 **Примеры:**\n"
            for example in examples[:2]:
                text += f"   ```\n   {example}\n   ```\n"
    return text


@mcp.tool()
async def get_quick_reference(
    element_name: Annotated[
        str,
        Field(description="Точное имя элемента, напр. \"СтрДлина\"."),
    ],
    object_name: Annotated[
        str | None,
        Field(description="Имя объекта для методов/свойств. Необязательно."),
    ] = None,
) -> str:
    """Короткая справка: только строка синтаксиса и одно предложение описания. Без параметров и примеров.

    ИСПОЛЬЗУЙ для быстрой сверки сигнатуры.
    Если нужны параметры или примеры — используй get_syntax_info.

    Пример: get_quick_reference(element_name="СтрДлина")
    """
    result = await _service().get_detailed_syntax_info(
        element_name, object_name, include_examples=False
    )
    if not result:
        return formatting.not_found(f"Элемент '{element_name}'")
    return formatting.quick_reference(result)


@mcp.tool()
async def search_by_context(
    query: Annotated[
        str,
        Field(description="Поисковая строка на русском."),
    ],
    context: Annotated[
        str,
        Field(description='Обязательно одно из: "global" (глобальные функции), "object" (члены объектов), "all" (везде).'),
    ],
    object_name: Annotated[
        str | None,
        Field(description='Ограничить конкретным объектом (только при context="object"). Необязательно.'),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Сколько результатов вернуть. По умолчанию 10."),
    ] = 10,
) -> str:
    """Поиск по справке с ограничением области: глобальные функции / члены объектов / везде.

    ИСПОЛЬЗУЙ, когда нужно сузить область поиска.
    Для свободного поиска без ограничений используй find_1c_help.

    Пример: search_by_context(query="Добавить", context="global", limit=5)
    """
    results = await _service().search_with_context_filter(
        query, context, object_name, limit
    )
    if results.get("error"):
        return f"Ошибка поиска: {results['error']}"
    if not results.get("results"):
        context_name = {"global": "глобальном", "object": "объектном", "all": "любом"}
        return formatting.not_found(
            query, f"{context_name.get(context, context)} контексте"
        )
    return formatting.context_search(results["results"], query, context)


@mcp.tool()
async def list_object_members(
    object_name: Annotated[
        str,
        Field(description='Точное имя объекта 1С, напр. "ТаблицаЗначений", "Массив".'),
    ],
    member_type: Annotated[
        str,
        Field(description='Тип элементов: "all" | "methods" | "properties" | "events". По умолчанию "all".'),
    ] = "all",
    limit: Annotated[
        int,
        Field(description="Сколько элементов вернуть. По умолчанию 50."),
    ] = 50,
) -> str:
    """Список методов, свойств и событий одного объекта 1С по имени объекта.

    ИСПОЛЬЗУЙ, когда нужен полный перечень членов объекта.
    НЕ ИСПОЛЬЗУЙ для поиска элемента по описанию — это find_1c_help.

    Пример: list_object_members(object_name="ТаблицаЗначений", member_type="methods")
    """
    result = await _service().get_object_members_list(object_name, member_type, limit)
    if result.get("error"):
        return f"Ошибка: {result['error']}"
    if result.get("total", 0) == 0:
        return formatting.not_found(
            f"Объект '{object_name}' не найден или не содержит элементов"
        )
    return formatting.object_members(
        object_name,
        member_type,
        result.get("methods", []),
        result.get("properties", []),
        result.get("events", []),
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=int(os.environ.get("MCP_PORT", settings.mcp_port)),
    )
