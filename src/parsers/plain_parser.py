"""Парсер «плоских» .hbk-архивов: статьи, справка, шаблоны синтаксиса.

Используется для корпусов, отличных от контекстной справки (язык запросов,
руководство, конструкции языка), где файлы лежат без структуры objects/.
"""

import html as html_lib
import re
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from src.core.logging import get_logger
from src.core.utils import (
    create_safe_temp_dir,
    safe_remove_dir,
    safe_subprocess_run,
)
from src.models.doc_models import Documentation, DocumentType

logger = get_logger(__name__)

SKIP_EXT = {".gif", ".png", ".jpg", ".jpeg", ".css", ".js", ".bmp", ".ico"}
SKIP_NAMES = {"__categories__"}
SKIP_PREFIX = "_CONTENTS_NODE_"

_ST_RE = re.compile(
    r'\{"(ru|en)",\s*\d+,\s*\d+,\s*"[^"]*",\s*"([^"]*)"\}'
)


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _extract(html_text: str, stem: str) -> tuple[str, str]:
    """Возвращает (заголовок, текст)."""
    soup = BeautifulSoup(html_text, "html.parser")
    title = ""
    for tag in ("h1", "h2", "h3", "title"):
        element = soup.find(tag)
        if element:
            candidate = element.get_text(" ", strip=True)
            if candidate:
                title = candidate
                break

    text = html_lib.unescape(re.sub(r"\s+", " ", soup.get_text(" ", strip=True))).strip()
    if not title:
        title = re.split(r"[.\n]", text, maxsplit=1)[0].strip() or stem
    return title[:200], text


def _parse_st_template(text: str, stem: str, source: str) -> Documentation | None:
    pairs = {lang: syntax for lang, syntax in _ST_RE.findall(text)}
    syntax_ru = pairs.get("ru", "").strip()
    syntax_en = pairs.get("en", "").strip()
    if not syntax_ru and not syntax_en:
        return None
    name = syntax_ru or syntax_en or stem
    return Documentation(
        id=f"{source}:st:{stem}",
        type=DocumentType.SYNTAX_TEMPLATE,
        name=name,
        source=source,
        syntax_ru=syntax_ru,
        syntax_en=syntax_en,
        full_path=f"{source}.{name}",
        source_file=stem,
    )


class PlainParser:
    """Извлекает документы из архива с плоской структурой."""

    def __init__(self, source: str):
        self.source = source

    def parse_file(self, file_path: str) -> List[Documentation]:
        tmp_dir = create_safe_temp_dir("hbk_plain_")
        documents: List[Documentation] = []
        try:
            # У .hbk нет нормального central directory, 7z извлекает часть файлов
            # с ошибкой (exit 2). Терпим это, если файлы всё же появились.
            result = safe_subprocess_run(
                ["7z", "x", "-y", f"-o{tmp_dir}", str(file_path)], timeout=120
            )
            if result.returncode not in (0, 1, 2):
                logger.error(f"7z вернул код {result.returncode}: {result.stderr[:300]}")
                return []
            if result.returncode != 0:
                logger.warning(f"7z код {result.returncode} для {file_path}, разбираем извлечённое")

            for path in sorted(Path(tmp_dir).rglob("*")):
                if not path.is_file():
                    continue
                stem = path.stem
                if path.name in SKIP_NAMES or path.name.startswith(SKIP_PREFIX):
                    continue
                if path.suffix.lower() in SKIP_EXT:
                    continue

                raw = path.read_bytes()
                text = _decode(raw)

                if path.suffix.lower() == ".st":
                    doc = _parse_st_template(text, stem, self.source)
                    if doc:
                        documents.append(doc)
                    continue

                title, body = _extract(text, stem)
                if not body:
                    continue
                documents.append(
                    Documentation(
                        id=f"{self.source}:{stem}",
                        type=DocumentType.REFERENCE,
                        name=title,
                        source=self.source,
                        description=body,
                        full_path=f"{self.source}.{title}",
                        source_file=path.name,
                    )
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Ошибка парсинга архива {file_path}: {e}")
        finally:
            safe_remove_dir(tmp_dir)
        return documents
