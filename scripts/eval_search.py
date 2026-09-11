"""Eval качества поиска: description-запросы → ожидаемый элемент.

Меряет Recall@1/@3/@5 и MRR текущего (лексического) поиска.
Запуск:
    python -m scripts.eval_search
"""

import asyncio
import re

from src.core.elasticsearch import get_es_client
from src.search.search_service import SearchService

# (запрос, ожидаемое имя, ожидаемый объект или None)
CASES: list[tuple[str, str, str | None]] = [
    ("посчитать длину строки", "СтрДлина", None),
    ("количество символов в строке", "СтрДлина", None),
    ("преобразовать строку в число", "Число", None),
    ("преобразовать число в строку", "Строка", None),
    ("получить текущую дату", "ТекущаяДата", None),
    ("округлить число", "Окр", None),
    ("найти подстроку в строке", "СтрНайти", None),
    ("заменить часть строки", "СтрЗаменить", None),
    ("разделить строку на подстроки", "СтрРазделить", None),
    ("убрать пробелы в начале и конце строки", "СокрЛП", None),
    ("привести строку к верхнему регистру", "ВРег", None),
    ("проверить что строка пустая", "ПустаяСтрока", None),
    ("число прописью", "ЧислоПрописью", None),
    ("добавить элемент в массив", "Добавить", "Массив"),
    ("количество элементов в массиве", "Количество", "Массив"),
    ("найти элемент в массиве", "Найти", "Массив"),
    ("удалить элемент из массива", "Удалить", "Массив"),
    ("отсортировать массив", "Сортировать", "Массив"),
    ("добавить строку в таблицу значений", "Добавить", "ТаблицаЗначений"),
    ("получить значение по индексу в таблице значений", "Получить", "ТаблицаЗначений"),
    ("скопировать таблицу значений", "Скопировать", "ТаблицаЗначений"),
    ("свернуть таблицу значений", "Свернуть", "ТаблицаЗначений"),
    ("записать событие в журнал регистрации", "ЗаписьЖурналаРегистрации", None),
    ("выполнить запрос к базе данных", "Выполнить", "Запрос"),
    ("начало дня", "НачалоДня", None),
    ("последний день месяца", "КонецМесяца", None),
    ("начало месяца", "НачалоМесяца", None),
    ("добавить месяц к дате", "ДобавитьМесяц", None),
    ("значение по имени колонки таблицы значений", "Найти", "КолонкиТаблицыЗначений"),
    ("установить значение элемента структуры", "Вставить", "Структура"),
]

TOP_K = 5


def _matches(res, name, obj) -> bool:
    res_name = re.sub(r"\s*\(.*\)\s*$", "", res.get("name", "")).strip()
    if res_name != name:
        return False
    if obj is None:
        return res.get("object") in (None, "Global context")
    return res.get("object") == obj


def _rank(results, name, obj):
    for i, res in enumerate(results, 1):
        if _matches(res, name, obj):
            return i
    return None


async def _target_exists(service, name, obj) -> bool:
    must = [{"match_phrase": {"name": name}}]
    must.append({"term": {"object": obj if obj is not None else "Global context"}})
    response = await service.es_client.search(
        {
            "query": {"bool": {"must": must}},
            "size": 5,
            "_source": ["name", "object"],
        }
    )
    for hit in response.get("hits", {}).get("hits", []):
        if _matches(hit.get("_source", {}), name, obj):
            return True
    return False


async def main():
    service = SearchService(get_es_client())
    if not await service.es_client.ensure_connected():
        print("Elasticsearch недоступен")
        return
    hits_at = {1: 0, 3: 0, 5: 0}
    rr_sum = 0.0
    misses = []
    skipped = []

    for query, name, obj in CASES:
        target = name if obj is None else f"{obj}.{name}"
        if not await _target_exists(service, name, obj):
            skipped.append(target)
            print(f"  N/A        '{query}' -> {target} (нет в индексе)")
            continue
        response = await service.find_help_by_query(query, limit=TOP_K)
        results = response.get("results", [])
        rank = _rank(results, name, obj)
        if rank:
            for k in hits_at:
                if rank <= k:
                    hits_at[k] += 1
            rr_sum += 1 / rank
            print(f"  ok   r{rank}  '{query}' -> {target}")
        else:
            misses.append((query, target, [r.get("name") for r in results[:3]]))
            print(f"  MISS       '{query}' -> {target}")

    total = len(CASES) - len(skipped)
    print(f"\nЦелей существует: {total} (пропущено {len(skipped)}: {skipped})")
    if total:
        print(f"Recall@1: {hits_at[1]}/{total} = {hits_at[1]/total:.0%}")
        print(f"Recall@3: {hits_at[3]}/{total} = {hits_at[3]/total:.0%}")
        print(f"Recall@5: {hits_at[5]}/{total} = {hits_at[5]/total:.0%}")
        print(f"MRR:      {rr_sum/total:.3f}")
    if misses:
        print("\nПромахи (top-3 фактически):")
        for query, target, got in misses:
            print(f"  '{query}' -> ждали {target}, получили {got}")


if __name__ == "__main__":
    asyncio.run(main())
