from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .text_utils import (
    chapter_from_hs,
    chapter_specific_rule_blocks,
    count_distinct_user_products,
    distinct_positions,
    has_material_composition_pattern,
    hs_digit_count,
    label_looks_like_container,
    listed_component_lines,
    mentions_assortment,
    mentions_integrated_product,
    mentions_rgi2a_product,
    normalize,
    position_from_hs,
)
from .types import RgiPipelineResult, RgiRuleRecord
from ..tariff_labels import lookup_position_label
from ..tariff_notes import get_chapter_explanatory_notes


def _score_essential_candidate(item: dict[str, Any], *, source_text: str, rank_index: int) -> float:
    description = str(item.get("description") or "")
    justification = str(item.get("justification") or "")
    combined = f"{description} {justification}"
    norm_desc = normalize(description)
    norm_source = normalize(source_text)

    score = float(item.get("confidence") or 55) * 0.4
    label = lookup_position_label(str(item.get("hs_code") or "")) or ""
    if label and not label_looks_like_container(label):
        score += 18
    if label and label_looks_like_container(label):
        score -= 22
    if norm_desc and norm_desc in norm_source:
        score += 12
    if rank_index == 0:
        score += 8

    listed = listed_component_lines(source_text)
    if listed:
        first = normalize(listed[0])
        if first and (first in norm_desc or norm_desc in first):
            score += 20

    value = str(item.get("value") or "")
    if value and re.search(r"\d", value) and "non renseign" not in normalize(value):
        score += 5
    if len(description.split()) >= 4:
        score += 6
    if re.search(r"\b(?:accessoire|emballage|etui|boite|coffret|verre|tire)\b", combined, re.I):
        score -= 10
    return score


def _specificity_score(item: dict[str, Any]) -> float:
    hs = str(item.get("hs_code") or "")
    label = lookup_position_label(hs) or ""
    score = float(hs_digit_count(hs))
    if label:
        score += min(len(label), 120) * 0.05
    try:
        score += float(item.get("confidence") or 0) * 0.1
    except (TypeError, ValueError):
        pass
    return score


def _hs_numeric_sort_key(hs_code: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.sub(r"\D", " ", hs_code).split() if p.isdigit()]
    return tuple(parts)


def _build_justification(result: RgiPipelineResult, retained_code: str) -> str:
    applied = "; ".join(
        f"{r.rule} ({r.reason})" for r in result.applied_rules if r.applied and r.reason
    )
    not_applied = "; ".join(
        f"{r.rule} non applicable ({r.reason})"
        for r in result.not_applied_rules
        if not r.applied and r.reason
    )
    studied = ", ".join(result.positions_studied[:8])
    rejected = ", ".join(result.positions_rejected[:8])
    parts = []
    if applied:
        parts.append(f"RGI appliquees : {applied}.")
    if not_applied:
        parts.append(not_applied + ".")
    if result.essential_character:
        parts.append(f"Caractere essentiel : {result.essential_character}.")
    if studied:
        parts.append(f"Positions etudiees : {studied}.")
    if rejected:
        parts.append(f"Positions ecartees : {rejected}.")
    if result.missing_information:
        parts.append("Informations manquantes : " + "; ".join(result.missing_information) + ".")
    parts.append(f"Classement retenu : {retained_code}.")
    return " ".join(parts)


@dataclass
class _PipelineState:
    source_text: str
    items: list[dict[str, Any]]
    result: RgiPipelineResult
    stop: bool = False
    merge_to_one: bool = False
    retained_index: int = 0
    notes_consulted: list[str] = field(default_factory=list)

    def record_applied(self, rule: str, reason: str) -> None:
        self.result.applied_rules.append(RgiRuleRecord(rule=rule, applied=True, reason=reason))

    def record_not_applied(self, rule: str, reason: str) -> None:
        self.result.not_applied_rules.append(RgiRuleRecord(rule=rule, applied=False, reason=reason))


class RgiPipeline:
    """Pipeline sequentiel RGI 1 -> 2 -> 3 (a,b,c) -> 4 -> 5 -> 6."""

    def run(self, source_text: str, items: list[dict[str, Any]]) -> RgiPipelineResult:
        state = _PipelineState(
            source_text=source_text,
            items=[dict(item) for item in items if isinstance(item, dict)],
            result=RgiPipelineResult(source_text=source_text),
        )
        if not state.items:
            state.record_not_applied("RGI 1", "Aucune classification LLM a analyser.")
            state.result.stopped_at = "empty"
            return state.result

        self._consult_notes(state)
        if count_distinct_user_products(source_text) > 1:
            state.record_applied("RGI 1", "Plusieurs marchandises distinctes demandees : une ligne par produit.")
            state.result.classifications = state.items
            state.result.stopped_at = "multi_product"
            state.stop = True
            return state.result

        self._stage_rgi1(state)
        if state.stop:
            return self._finalize(state)

        self._stage_rgi2(state)
        if state.stop:
            return self._finalize(state)

        self._stage_rgi3(state)
        if state.stop:
            return self._finalize(state)

        self._stage_rgi4(state)
        self._stage_rgi5(state)
        self._stage_rgi6(state)
        return self._finalize(state)

    def _consult_notes(self, state: _PipelineState) -> None:
        chapters = {
            chapter_from_hs(item.get("hs_code")) or str(item.get("chapter") or "").strip()
            for item in state.items
        }
        for ch in sorted(ch for ch in chapters if ch):
            notes = get_chapter_explanatory_notes(ch)
            if notes:
                state.notes_consulted.extend(notes[:2])
        if state.notes_consulted:
            state.record_applied(
                "Notes legales",
                f"Notes de chapitre consultees ({len(state.notes_consulted)} extrait(s) TEC).",
            )

    def _stage_rgi1(self, state: _PipelineState) -> None:
        subposition_pending = any(
            chapter_specific_rule_blocks(item, state.source_text) for item in state.items
        )

        if len(state.items) == 1:
            item = state.items[0]
            pos = position_from_hs(item.get("hs_code")) or str(item.get("hs_code") or "")
            label = lookup_position_label(pos) or lookup_position_label(str(item.get("hs_code") or ""))
            if label or pos:
                reason = f"Position {pos} retenue selon le libelle TEC"
                if label:
                    reason += f" ({label[:80]})"
                if subposition_pending:
                    reason += " ; sous-position a preciser selon les criteres TEC"
                state.record_applied("RGI 1", reason + ".")
                state.stop = True
                state.result.stopped_at = "RGI 1"
                return

            if has_material_composition_pattern(state.source_text) and not mentions_assortment(state.source_text):
                state.record_applied(
                    "RGI 1",
                    "Produit composite : les notes du chapitre priment sur une simple proportion de matieres.",
                )
                state.stop = True
                state.result.stopped_at = "RGI 1"
                return

            state.record_applied("RGI 1", "Une seule ligne retenue ; position a confirmer avec le libelle TEC.")
            state.stop = True
            state.result.stopped_at = "RGI 1"
            return

        state.record_not_applied(
            "RGI 1",
            "Plusieurs lignes LLM : la description ne correspond pas a une seule position directe.",
        )

    def _stage_rgi2(self, state: _PipelineState) -> None:
        if mentions_rgi2a_product(state.source_text):
            state.record_applied(
                "RGI 2 a",
                "Produit incomplet, demonte ou non monte : classe comme le produit fini si caracteristiques essentielles.",
            )
        else:
            state.record_not_applied("RGI 2 a", "Produit fini ou monte : regle non declenchee.")

        if has_material_composition_pattern(state.source_text) and not mentions_assortment(state.source_text):
            state.record_applied(
                "RGI 2 b",
                "Plusieurs matieres : plusieurs positions peuvent etre envisageables ; poursuite vers RGI 3.",
            )
        elif len(state.items) > 1:
            state.record_applied(
                "RGI 2 b",
                "Ensemble de composants : plusieurs positions envisageables ; poursuite vers RGI 3.",
            )
        else:
            state.record_not_applied("RGI 2 b", "Pas de melange de matieres declenchant un conflit de positions.")

    def _stage_rgi3(self, state: _PipelineState) -> None:
        items = state.items
        if len(items) <= 1:
            state.record_not_applied("RGI 3", "Une seule position candidate apres RGI 1.")
            state.stop = True
            state.result.stopped_at = "RGI 3"
            return

        if has_material_composition_pattern(state.source_text) and not mentions_assortment(state.source_text):
            state.record_not_applied(
                "RGI 3 b",
                "Produit a matieres multiples : regles de chapitre, pas assortiment.",
            )
            state.stop = True
            state.result.stopped_at = "RGI 2 b"
            state.result.classifications = items
            return

        is_assortment = mentions_assortment(state.source_text) or len(listed_component_lines(state.source_text)) >= 2
        is_decomposed = count_distinct_user_products(state.source_text) == 1
        is_integrated = mentions_integrated_product(state.source_text)

        if not is_assortment and not (is_decomposed and (is_integrated or len(distinct_positions(items)) >= 2)):
            state.record_not_applied("RGI 3", "Decomposition sans conflit de positions ni assortiment identifiable.")
            state.result.classifications = items
            state.stop = True
            state.result.stopped_at = "RGI 3"
            return

        state.result.positions_studied = sorted(
            position_from_hs(item.get("hs_code")) or f"ch{item.get('chapter', '')}"
            for item in items
            if item.get("hs_code") or item.get("chapter")
        )

        ranked = sorted(
            enumerate(items),
            key=lambda pair: _specificity_score(pair[1]),
            reverse=True,
        )
        top_idx, top_item = ranked[0]
        second_score = _specificity_score(ranked[1][1]) if len(ranked) > 1 else 0.0
        top_spec = _specificity_score(top_item)

        if top_spec - second_score >= 15 and hs_digit_count(top_item.get("hs_code")) >= hs_digit_count(
            ranked[1][1].get("hs_code") if len(ranked) > 1 else ""
        ):
            state.record_applied(
                "RGI 3 a",
                f"Position {top_item.get('hs_code')} plus specifique que les autres candidates.",
            )
            state.merge_to_one = True
            state.retained_index = top_idx
            state.result.positions_rejected = [
                str(items[i].get("hs_code") or items[i].get("description") or "")
                for i, _ in ranked[1:]
            ]
            state.stop = True
            state.result.stopped_at = "RGI 3 a"
            return

        state.record_not_applied(
            "RGI 3 a",
            "Aucune position manifestement plus specifique que les autres.",
        )

        scored = [
            (_score_essential_candidate(item, source_text=state.source_text, rank_index=idx), idx, item)
            for idx, item in enumerate(items)
        ]
        scored.sort(key=lambda row: row[0], reverse=True)
        top_score, top_idx, top_item = scored[0]
        second_score_essential = scored[1][0] if len(scored) > 1 else 0.0

        if top_score < 45 or (len(scored) > 1 and (top_score - second_score_essential) < 12):
            if len(scored) > 1 and abs(top_spec - second_score) < 8:
                c_idx = max(
                    range(len(items)),
                    key=lambda i: _hs_numeric_sort_key(str(items[i].get("hs_code") or "0")),
                )
                state.record_applied(
                    "RGI 3 c",
                    "Dernier recours : position la plus elevee par ordre numerique parmi les candidates.",
                )
                state.merge_to_one = True
                state.retained_index = c_idx
                state.result.confidence_cap = 55
                state.result.positions_rejected = [
                    str(items[i].get("hs_code") or "") for i in range(len(items)) if i != c_idx
                ]
                state.stop = True
                state.result.stopped_at = "RGI 3 c"
                return

            state.record_not_applied(
                "RGI 3 b",
                "Caractere essentiel indeterminable avec certitude suffisante.",
            )
            state.record_not_applied(
                "RGI 3 c",
                "Informations insuffisantes pour appliquer le dernier recours numerique.",
            )
            state.result.missing_information = [
                "Preciser l'element donnant l'identite commerciale ou la fonction principale de l'ensemble.",
                "Confirmer s'il s'agit d'un assortiment ou d'un produit integre.",
            ]
            state.result.confidence_cap = 60
            for item in items:
                item["classification_status"] = "provisoire"
            state.result.classifications = items
            state.stop = True
            state.result.stopped_at = "RGI 3 b"
            return

        essential = str(top_item.get("description") or "").strip()
        state.result.essential_character = essential
        state.result.positions_rejected = [
            str(items[idx].get("hs_code") or items[idx].get("description") or "")
            for _, idx, _ in scored[1:]
        ]
        reason = "Assortiment ou produit integre : caractere essentiel determine apres ponderation des criteres."
        state.record_applied("RGI 3 b", reason)
        state.merge_to_one = True
        state.retained_index = top_idx
        state.result.confidence_cap = min(95, int(top_score))
        state.stop = True
        state.result.stopped_at = "RGI 3 b"

    def _stage_rgi4(self, state: _PipelineState) -> None:
        if state.stop:
            return
        state.record_not_applied(
            "RGI 4",
            "Des positions du TEC restent applicables : analogie non necessaire.",
        )

    def _stage_rgi5(self, state: _PipelineState) -> None:
        state.record_not_applied(
            "RGI 5",
            "Emballages et contenants integres au produit : pas de ligne separee pour composants internes.",
        )

    def _stage_rgi6(self, state: _PipelineState) -> None:
        for item in state.result.classifications or state.items:
            if chapter_specific_rule_blocks(item, state.source_text):
                state.record_applied(
                    "RGI 6",
                    "Sous-position non determinable : arret au niveau de la position (4 chiffres).",
                )
                hs = str(item.get("hs_code") or "")
                pos = position_from_hs(hs)
                if pos and hs_digit_count(hs) > 4:
                    item["hs_code"] = pos
                    item["subposition_status"] = "a_determiner"
                if state.result.confidence_cap is None:
                    state.result.confidence_cap = 65
                return
        state.record_applied(
            "RGI 6",
            "Sous-position proposee dans la meme position retenue.",
        )

    def _finalize(self, state: _PipelineState) -> RgiPipelineResult:
        if state.merge_to_one and len(state.items) > 1:
            retained = dict(state.items[state.retained_index])
            retained_code = str(retained.get("hs_code") or "")
            retained["description"] = (
                str(retained.get("description") or "").strip()
                or state.source_text.splitlines()[0][:240]
            )
            if state.result.confidence_cap is not None:
                try:
                    current = int(retained.get("confidence") or 0)
                except (TypeError, ValueError):
                    current = 0
                retained["confidence"] = min(current or state.result.confidence_cap, state.result.confidence_cap)
            state.result.classifications = [retained]
        elif not state.result.classifications:
            for item in state.items:
                item = dict(item)
                if state.result.confidence_cap is not None:
                    try:
                        current = int(item.get("confidence") or 0)
                    except (TypeError, ValueError):
                        current = 0
                    item["confidence"] = min(current or state.result.confidence_cap, state.result.confidence_cap)
                state.result.classifications.append(item)

        for item in state.result.classifications:
            item["rgi_pipeline"] = state.result.to_dict()
            item["rgi_3b"] = {
                "applicable": any(r.rule == "RGI 3 b" and r.applied for r in state.result.applied_rules),
                "applied": state.result.stopped_at == "RGI 3 b" and state.merge_to_one,
                "essential_character": state.result.essential_character,
                "not_applicable_reason": next(
                    (r.reason for r in state.result.not_applied_rules if r.rule == "RGI 3 b"),
                    "",
                ),
            }
        return state.result


def apply_rgi_pipeline_to_response(data: dict[str, Any]) -> dict[str, Any]:
    classifications = data.get("classifications")
    if not isinstance(classifications, list):
        return data

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in classifications:
        if not isinstance(item, dict):
            continue
        key = str(item.get("source_query") or item.get("description") or "__default__").strip()
        groups.setdefault(key, []).append(item)

    pipeline = RgiPipeline()
    merged: list[dict[str, Any]] = []
    engine_log: list[dict[str, Any]] = []

    for source_key, items in groups.items():
        source_text = source_key if source_key != "__default__" else str(items[0].get("description") or "")
        result = pipeline.run(source_text, items)
        engine_log.append(result.to_dict())
        merged.extend(result.classifications)

    data["classifications"] = merged
    if engine_log:
        data["rgi_engine"] = engine_log
    return data
