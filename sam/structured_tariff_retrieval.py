"""Zero-API lexical retrieval over the structured official TEC hierarchy."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
import unicodedata

from .tariff_hierarchy import TariffHierarchy


_STOPWORDS = {
    "a", "au", "aux", "avec", "and", "article", "articles", "autre", "autres",
    "dans", "de", "des", "du", "en", "et", "for", "la", "le", "les", "of",
    "ou", "par", "pour", "the", "un", "une", "usage", "with",
}


def _tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    tokens: list[str] = []
    for token in re.findall(r"[a-z0-9]+", normalized):
        if len(token) < 3 or token in _STOPWORDS or token.isdigit():
            continue
        # A conservative plural fold covers common French/English label
        # variants without introducing product-family aliases.
        if len(token) >= 5 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


@dataclass(frozen=True)
class StructuredTariffMatch:
    position_code: str
    label: str
    score: float
    matched_terms: tuple[str, ...]

    def to_candidate(self) -> dict[str, object]:
        return {
            "position_code": self.position_code,
            "label": self.label,
            "score": round(self.score, 4),
            "chapter": re.sub(r"\D", "", self.position_code)[:2],
            "excerpt": "",
            "matched_codes": [],
            "matched_terms": list(self.matched_terms),
            "candidate_sources": ["structured_lexical"],
        }


class StructuredTariffRetriever:
    """Small BM25 index grouped by official four-digit heading."""

    def __init__(self, hierarchy: TariffHierarchy) -> None:
        self.hierarchy = hierarchy
        texts: dict[str, list[str]] = defaultdict(list)
        for node in hierarchy.nodes.values():
            heading_digits = node.code_digits[:4]
            if node.label:
                texts[heading_digits].append(node.label)
            if node.chapter_label:
                texts[heading_digits].append(node.chapter_label)

        self._term_frequencies: dict[str, Counter[str]] = {}
        document_frequency: Counter[str] = Counter()
        total_length = 0
        for heading_digits, fragments in texts.items():
            frequencies = Counter(_tokens(" ".join(dict.fromkeys(fragments))))
            self._term_frequencies[heading_digits] = frequencies
            document_frequency.update(frequencies.keys())
            total_length += sum(frequencies.values())

        self._document_frequency = document_frequency
        self._document_count = len(self._term_frequencies)
        self._average_length = (
            total_length / self._document_count if self._document_count else 1.0
        )

    @property
    def document_count(self) -> int:
        return self._document_count

    def search(self, query: str, *, top_n: int = 6) -> list[StructuredTariffMatch]:
        query_terms = tuple(dict.fromkeys(_tokens(query)))
        if not query_terms or not self._document_count:
            return []

        k1 = 1.5
        b = 0.75
        scored: list[tuple[str, float, tuple[str, ...]]] = []
        for heading_digits, frequencies in self._term_frequencies.items():
            document_length = max(sum(frequencies.values()), 1)
            score = 0.0
            matched: list[str] = []
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                matched.append(term)
                document_frequency = self._document_frequency.get(term, 0)
                inverse_frequency = math.log(
                    1 + (self._document_count - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                denominator = frequency + k1 * (
                    1 - b + b * document_length / self._average_length
                )
                score += inverse_frequency * (frequency * (k1 + 1) / denominator)
            if score > 0:
                scored.append((heading_digits, score, tuple(matched)))

        scored.sort(key=lambda item: (-item[1], item[0]))
        strongest = scored[0][1] if scored else 1.0
        matches: list[StructuredTariffMatch] = []
        for heading_digits, raw_score, matched_terms in scored[: max(1, top_n)]:
            node = self.hierarchy.get(heading_digits)
            if node is None:
                continue
            matches.append(
                StructuredTariffMatch(
                    position_code=node.code,
                    label=node.label,
                    score=2.5 * raw_score / strongest,
                    matched_terms=matched_terms,
                )
            )
        return matches


_STRUCTURED_RETRIEVER: StructuredTariffRetriever | None = None


def set_structured_tariff_retriever(retriever: StructuredTariffRetriever) -> None:
    global _STRUCTURED_RETRIEVER
    _STRUCTURED_RETRIEVER = retriever


def get_structured_tariff_retriever() -> StructuredTariffRetriever | None:
    return _STRUCTURED_RETRIEVER


def search_structured_tariff_positions(
    query: str,
    *,
    top_n: int = 6,
) -> list[dict[str, object]]:
    retriever = get_structured_tariff_retriever()
    if retriever is None:
        return []
    return [match.to_candidate() for match in retriever.search(query, top_n=top_n)]
