"""Форматирование MCP-ответов в человекочитаемый текст."""

from typing import Any, Dict, List


def not_found(query: str, context: str = "") -> str:
    """Текст ответа для случая «ничего не найдено»."""
    if context:
        return f"По запросу '{query}' в контексте '{context}' ничего не найдено."
    return f"По запросу '{query}' ничего не найдено."


def search_results(results: List[Dict[str, Any]], query: str) -> str:
    """Форматирует список результатов поиска."""
    text = f"📋 **Найдено:** {len(results)} элементов по запросу \"{query}\"\n\n"
    for i, result in enumerate(results, 1):
        name = result.get("name", "")
        obj = result.get("object", "")
        description = result.get("description", "")
        text += f"{i}. **{name}**"
        if obj:
            text += " (Глобальная функция)" if obj == "Global context" else f" ({obj} → Метод)"
        if description:
            desc = description[:100] + "..." if len(description) > 100 else description
            text += f"\n   └ {desc}"
        text += "\n"
    return text


def syntax_info(result: Dict[str, Any]) -> str:
    """Форматирует полную техническую справку."""
    text = f"🔧 **ТЕХНИЧЕСКАЯ СПРАВКА:** {result.get('name', '')}"
    if result.get("object"):
        text += f" ({result['object']})"
    text += "\n\n"

    if result.get("description"):
        text += f"📝 **Описание:**\n   {result['description']}\n\n"

    if result.get("syntax_ru"):
        text += f"🔤 **Синтаксис:**\n   `{result['syntax_ru']}`\n\n"

    parameters = result.get("parameters")
    if parameters and isinstance(parameters, list):
        text += "⚙️ **Параметры:**\n"
        for param in parameters:
            if isinstance(param, dict):
                required = " (обязательный)" if param.get("required") else " (необязательный)"
                text += f"   • {param.get('name', '')} ({param.get('type', '')}){required}"
                if param.get("description"):
                    text += f" - {param['description']}"
                text += "\n"
        text += "\n"

    if result.get("return_type"):
        text += f"↩️ **Возвращает:** {result['return_type']}\n\n"

    return text


def quick_reference(result: Dict[str, Any]) -> str:
    """Форматирует краткую справку."""
    name = result.get("name", "")
    syntax = result.get("syntax_ru", "")
    description = result.get("description", "")

    text = "⚡ **КРАТКАЯ СПРАВКА**\n\n"
    text += f"`{syntax}`\n" if syntax else f"`{name}`\n"

    if description:
        desc = description.split(".")[0] + "." if "." in description else description
        desc = desc[:100] + "..." if len(desc) > 100 else desc
        text += f"└ {desc}"

    return text


def context_search(results: List[Dict[str, Any]], query: str, context: str) -> str:
    """Форматирует результаты контекстного поиска."""
    if context == "object":
        objects: Dict[str, List[Dict[str, Any]]] = {}
        for result in results:
            obj = result.get("object", "Неизвестно")
            objects.setdefault(obj, []).append(result)

        text = f"🎯 **ПОИСК В КОНТЕКСТЕ:** {context}\n\n"
        text += f"Найдено {len(results)} элементов по запросу \"{query}\"\n\n"
        for obj, items in list(objects.items())[:5]:
            text += f"📦 **{obj}:**\n"
            for item in items[:3]:
                name = item.get("name", "")
                syntax = item.get("syntax_ru", "")
                desc = item.get("description", "")
                text += f"   • {name}"
                if syntax:
                    text += f" - `{syntax}`"
                if desc:
                    short_desc = desc[:50] + "..." if len(desc) > 50 else desc
                    text += f"\n     {short_desc}"
                text += "\n"
            text += "\n"
        return text

    text = f"🔍 **ПОИСК В КОНТЕКСТЕ:** {context}\n\n"
    text += f"Найдено {len(results)} элементов\n\n"
    for i, result in enumerate(results[:8], 1):
        name = result.get("name", "")
        syntax = result.get("syntax_ru", "")
        text += f"{i}. **{name}**"
        if syntax:
            text += f" - `{syntax}`"
        text += "\n"
    return text


def object_members(
    object_name: str,
    member_type: str,
    methods: List[Dict[str, Any]],
    properties: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
) -> str:
    """Форматирует список элементов объекта."""
    text = f"📦 **ОБЪЕКТ:** {object_name}\n\n"

    if member_type in ("all", "methods") and methods:
        text += f"🔨 **Методы ({len(methods)}):**\n"
        for method in methods[:20]:
            name = method.get("name", "")
            syntax = method.get("syntax_ru", "")
            desc = method.get("description", "")
            text += f"   • **{name}**"
            if syntax:
                text += f" - `{syntax}`"
            if desc:
                short_desc = desc[:80] + "..." if len(desc) > 80 else desc
                text += f"\n     {short_desc}"
            text += "\n"
        text += "\n"

    if member_type in ("all", "properties") and properties:
        text += f"📋 **Свойства ({len(properties)}):**\n"
        for prop in properties[:15]:
            name = prop.get("name", "")
            desc = prop.get("description", "")
            text += f"   • **{name}**"
            if desc:
                short_desc = desc[:60] + "..." if len(desc) > 60 else desc
                text += f" - {short_desc}"
            text += "\n"
        text += "\n"

    if member_type in ("all", "events") and events:
        text += f"⚡ **События ({len(events)}):**\n"
        for event in events[:10]:
            name = event.get("name", "")
            desc = event.get("description", "")
            text += f"   • **{name}**"
            if desc:
                short_desc = desc[:60] + "..." if len(desc) > 60 else desc
                text += f" - {short_desc}"
            text += "\n"

    return text
