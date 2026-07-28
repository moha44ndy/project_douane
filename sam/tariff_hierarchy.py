"""Structured CEDEAO/TEC tariff hierarchy built from parsed official indexes.

This module does not infer tariff positions from products. It only turns the
codes already extracted from the official nomenclature into a validated tree
that retrieval and decision stages can consume without depending on PDF chunk
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping


_LEVEL_BY_LENGTH = {
    4: "heading",
    6: "hs_subheading",
    8: "tec_subheading",
    10: "national_line",
}

_SECTION_CHAPTER_RANGES: tuple[tuple[str, int, int], ...] = (
    ("I", 1, 5),
    ("II", 6, 14),
    ("III", 15, 15),
    ("IV", 16, 24),
    ("V", 25, 27),
    ("VI", 28, 38),
    ("VII", 39, 40),
    ("VIII", 41, 43),
    ("IX", 44, 46),
    ("X", 47, 49),
    ("XI", 50, 63),
    ("XII", 64, 67),
    ("XIII", 68, 70),
    ("XIV", 71, 71),
    ("XV", 72, 83),
    ("XVI", 84, 85),
    ("XVII", 86, 89),
    ("XVIII", 90, 92),
    ("XIX", 93, 93),
    ("XX", 94, 96),
    ("XXI", 97, 97),
)


def normalize_tariff_code(value: str) -> str:
    """Return a supported 4/6/8/10-digit code, or an empty string."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) in _LEVEL_BY_LENGTH else ""


def format_tariff_code(code_digits: str) -> str:
    """Format normalized code digits using the notation used by the TEC."""
    digits = normalize_tariff_code(code_digits)
    if not digits:
        return ""
    if len(digits) == 4:
        return f"{digits[:2]}.{digits[2:4]}"
    groups = [digits[:4], digits[4:6]]
    if len(digits) >= 8:
        groups.append(digits[6:8])
    if len(digits) == 10:
        groups.append(digits[8:10])
    return ".".join(groups)


def section_for_chapter(chapter: int) -> str:
    for section, start, end in _SECTION_CHAPTER_RANGES:
        if start <= chapter <= end:
            return section
    return ""


@dataclass(frozen=True)
class TariffNode:
    code: str
    code_digits: str
    level: str
    parent_code: str | None
    section: str
    chapter: int
    chapter_label: str
    label: str
    full_label: str
    is_synthetic: bool
    rates: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TariffHierarchyValidation:
    node_count: int
    nodes_by_level: Mapping[str, int]
    source_node_count: int
    synthetic_node_count: int
    orphan_count: int
    invalid_source_codes: tuple[str, ...]
    missing_source_labels: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.orphan_count == 0 and not self.invalid_source_codes


@dataclass(frozen=True)
class TariffHierarchy:
    nodes: Mapping[str, TariffNode]
    children: Mapping[str, tuple[str, ...]]
    validation: TariffHierarchyValidation
    source_version: str = "TEC-SH-2022"

    def get(self, code: str) -> TariffNode | None:
        return self.nodes.get(normalize_tariff_code(code))

    def ancestors(self, code: str) -> tuple[TariffNode, ...]:
        """Return ancestors from the heading down to the direct parent."""
        node = self.get(code)
        if node is None:
            return ()
        result: list[TariffNode] = []
        parent_code = node.parent_code
        while parent_code:
            parent = self.nodes.get(parent_code)
            if parent is None:
                break
            result.append(parent)
            parent_code = parent.parent_code
        result.reverse()
        return tuple(result)

    def child_nodes(self, code: str) -> tuple[TariffNode, ...]:
        digits = normalize_tariff_code(code)
        return tuple(self.nodes[item] for item in self.children.get(digits, ()))


_TARIFF_HIERARCHY: TariffHierarchy | None = None


def _parent_code(code_digits: str) -> str | None:
    parent_length = {4: 0, 6: 4, 8: 6, 10: 8}[len(code_digits)]
    return code_digits[:parent_length] if parent_length else None


def _label_chain(
    code_digits: str,
    labels: Mapping[str, str],
    chapter_label: str,
) -> str:
    values: list[str] = []
    if chapter_label:
        values.append(chapter_label.strip())
    for length in (4, 6, 8, 10):
        if length > len(code_digits):
            break
        label = str(labels.get(code_digits[:length]) or "").strip()
        if label and label not in values:
            values.append(label)
    return " > ".join(values)


def build_tariff_hierarchy(
    tariff_labels: Mapping[str, str],
    position_labels: Mapping[str, str],
    chapter_titles: Mapping[int, str] | None = None,
    tariff_rates: Mapping[str, Mapping[str, str]] | None = None,
    *,
    source_version: str = "TEC-SH-2022",
) -> TariffHierarchy:
    """Build a parent-linked hierarchy from the official parsed indexes."""
    chapter_titles = chapter_titles or {}
    tariff_rates = tariff_rates or {}
    labels_by_digits: dict[str, str] = {}
    source_codes: set[str] = set()
    invalid_source_codes: list[str] = []
    missing_source_labels: list[str] = []

    for raw_code, raw_label in tariff_labels.items():
        digits = normalize_tariff_code(raw_code)
        if not digits or len(digits) < 6:
            invalid_source_codes.append(str(raw_code))
            continue
        label = str(raw_label or "").strip()
        if not label:
            missing_source_labels.append(str(raw_code))
            continue
        source_codes.add(digits)
        previous = labels_by_digits.get(digits, "")
        if len(label) > len(previous):
            labels_by_digits[digits] = label

    for raw_code, raw_label in position_labels.items():
        digits = normalize_tariff_code(raw_code)
        if len(digits) != 4:
            invalid_source_codes.append(str(raw_code))
            continue
        label = str(raw_label or "").strip()
        if not label:
            missing_source_labels.append(str(raw_code))
            continue
        source_codes.add(digits)
        labels_by_digits[digits] = label

    all_codes: set[str] = set()
    for code_digits in source_codes:
        for length in (4, 6, 8, 10):
            if length <= len(code_digits):
                all_codes.add(code_digits[:length])

    normalized_rates: dict[str, Mapping[str, str]] = {}
    for raw_code, rates in tariff_rates.items():
        digits = normalize_tariff_code(raw_code)
        if digits:
            normalized_rates[digits] = dict(rates)

    nodes: dict[str, TariffNode] = {}
    for code_digits in sorted(all_codes, key=lambda item: (len(item), item)):
        chapter = int(code_digits[:2])
        chapter_label = str(chapter_titles.get(chapter) or "").strip()
        label = labels_by_digits.get(code_digits, "")
        nodes[code_digits] = TariffNode(
            code=format_tariff_code(code_digits),
            code_digits=code_digits,
            level=_LEVEL_BY_LENGTH[len(code_digits)],
            parent_code=_parent_code(code_digits),
            section=section_for_chapter(chapter),
            chapter=chapter,
            chapter_label=chapter_label,
            label=label,
            full_label=_label_chain(code_digits, labels_by_digits, chapter_label),
            is_synthetic=code_digits not in source_codes,
            rates=dict(normalized_rates.get(code_digits, {})),
        )

    children_lists: dict[str, list[str]] = {}
    orphan_count = 0
    for code_digits, node in nodes.items():
        if not node.parent_code:
            continue
        if node.parent_code not in nodes:
            orphan_count += 1
            continue
        children_lists.setdefault(node.parent_code, []).append(code_digits)

    children = {
        parent: tuple(sorted(child_codes))
        for parent, child_codes in children_lists.items()
    }
    nodes_by_level = {
        level: sum(1 for node in nodes.values() if node.level == level)
        for level in _LEVEL_BY_LENGTH.values()
    }
    validation = TariffHierarchyValidation(
        node_count=len(nodes),
        nodes_by_level=nodes_by_level,
        source_node_count=sum(1 for node in nodes.values() if not node.is_synthetic),
        synthetic_node_count=sum(1 for node in nodes.values() if node.is_synthetic),
        orphan_count=orphan_count,
        invalid_source_codes=tuple(sorted(set(invalid_source_codes))),
        missing_source_labels=tuple(sorted(set(missing_source_labels))),
    )
    return TariffHierarchy(
        nodes=nodes,
        children=children,
        validation=validation,
        source_version=source_version,
    )


def set_tariff_hierarchy(hierarchy: TariffHierarchy) -> None:
    global _TARIFF_HIERARCHY
    _TARIFF_HIERARCHY = hierarchy


def get_tariff_hierarchy() -> TariffHierarchy | None:
    return _TARIFF_HIERARCHY
