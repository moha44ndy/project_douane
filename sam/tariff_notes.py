"""Notes de chapitre extraites des chunks TEC (pas de texte juridique en dur)."""

from __future__ import annotations

import re
from typing import Iterable

_CHAPTER_HEADER_RE = re.compile(r"Chapitre\s+(\d{1,2})\b", re.IGNORECASE)
_CHAPTER_NOTE_LINE_RE = re.compile(r"^\s*\d+\s*\.-\s*(.+)$")
_TARIFF_POSITION_LINE_RE = re.compile(r"^\d{4}\.\d{2}(?:\.\d{2})?")

_CHAPTER_NOTES_INDEX: dict[int, list[str]] | None = None
_CHAPTER_TITLES_INDEX: dict[int, str] | None = None


def build_chapter_notes_index(chunks: Iterable) -> dict[int, list[str]]:
    """Indexe les notes de chapitre presentes dans les chunks TEC."""
    index: dict[int, list[str]] = {}
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        current_chapter: int | None = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            header = _CHAPTER_HEADER_RE.search(line)
            if header:
                try:
                    current_chapter = int(header.group(1))
                except ValueError:
                    current_chapter = None
            if current_chapter is None:
                continue
            note_match = _CHAPTER_NOTE_LINE_RE.match(line)
            if not note_match:
                continue
            note = re.sub(r"\s+", " ", note_match.group(1)).strip()
            if len(note) < 25:
                continue
            bucket = index.setdefault(current_chapter, [])
            if note not in bucket:
                bucket.append(note)
            if len(bucket) >= 6:
                continue
    return index


def _looks_like_tariff_label_line(line: str) -> bool:
    """Exclut les lignes de codes SH / sous-positions (pas un titre de chapitre)."""
    stripped = line.strip()
    if not stripped:
        return True
    if _TARIFF_POSITION_LINE_RE.match(stripped):
        return True
    if stripped.startswith("--"):
        return True
    if re.search(r"\d{4}\.\d{2}(?:\.\d{2})?", stripped[:16]):
        return True
    return False


def build_chapter_titles_index(chunks: Iterable) -> dict[int, str]:
    """Extrait les titres de chapitre depuis les en-tetes des chunks TEC."""
    index: dict[int, str] = {}
    for chunk in chunks:
        text = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        lines = [line.strip() for line in text.splitlines()]
        for idx, line in enumerate(lines):
            header = re.match(r"^Chapitre\s+(\d{1,2})\b", line, re.IGNORECASE)
            if not header:
                continue
            try:
                chapter = int(header.group(1))
            except ValueError:
                continue
            title_parts: list[str] = []
            for follow in lines[idx + 1 : idx + 6]:
                if not follow:
                    if title_parts:
                        break
                    continue
                if re.match(r"^Chapitre\s+\d", follow, re.IGNORECASE):
                    break
                if re.match(r"^N°\s*de\s*position", follow, re.IGNORECASE):
                    break
                if re.match(r"^Notes\.?", follow, re.IGNORECASE):
                    break
                if re.match(r"^\d+\s*\.-", follow):
                    break
                if _looks_like_tariff_label_line(follow):
                    break
                if len(follow) < 12:
                    continue
                title_parts.append(re.sub(r"\s+", " ", follow))
            if title_parts:
                index[chapter] = " ".join(title_parts)[:500]
    return index


def set_chapter_titles_index(index: dict[int, str]) -> None:
    global _CHAPTER_TITLES_INDEX
    _CHAPTER_TITLES_INDEX = index


def get_chapter_titles_index() -> dict[int, str]:
    return _CHAPTER_TITLES_INDEX or {}


def get_chapter_title(chapter: str | int) -> str:
    try:
        ch = int(str(chapter).lstrip("0") or "0")
    except ValueError:
        return ""
    return get_chapter_titles_index().get(ch, "")


def set_chapter_notes_index(index: dict[int, list[str]]) -> None:
    global _CHAPTER_NOTES_INDEX
    _CHAPTER_NOTES_INDEX = index


def get_chapter_notes_index() -> dict[int, list[str]]:
    return _CHAPTER_NOTES_INDEX or {}


def get_chapter_explanatory_notes(chapter: str | int) -> list[str]:
    try:
        ch = int(str(chapter).lstrip("0") or "0")
    except ValueError:
        return []
    return list(get_chapter_notes_index().get(ch, []))
