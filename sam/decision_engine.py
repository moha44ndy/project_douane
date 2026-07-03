"""Moteur de decision : le texte est produit a partir des decisions, pas l'inverse."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from .tariff_labels import lookup_position_label
from .tariff_metadata import get_full_chapter_name, get_position_heading
from .tariff_notes import get_chapter_explanatory_notes
from .tariff_position_rules import position_code_from_hs
from .tariff_subposition import (
    build_criteria_trace_from_tec,
    resolve_subposition_from_tec,
)

CriterionStatus = Literal["not_required", "required", "satisfied", "missing"]


@dataclass
class CriterionDecision:
    criterion_id: str
    label: str
    status: CriterionStatus
    tec_reference: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "criterion_id": self.criterion_id,
            "label": self.label,
            "status": self.status,
            "tec_reference": self.tec_reference,
            "detail": self.detail,
        }


@dataclass
class ClassificationDecision:
    product_identified: str
    position_code: str
    hs_code: str
    chapter: str
    classification_status: str
    subposition_status: str | None
    confidence: int
    criteria: list[CriterionDecision] = field(default_factory=list)
    missing_criteria: list[str] = field(default_factory=list)
    llm_hypothesis_hs: str = ""
    subposition_resolution: dict[str, Any] = field(default_factory=dict)
    rgi_applied: list[str] = field(default_factory=list)
    rgi_applied_records: list[dict[str, str]] = field(default_factory=list)
    rgi_not_applicable: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_identified": self.product_identified,
            "position_code": self.position_code,
            "hs_code": self.hs_code,
            "chapter": self.chapter,
            "classification_status": self.classification_status,
            "subposition_status": self.subposition_status,
            "confidence": self.confidence,
            "criteria": [c.to_dict() for c in self.criteria],
            "missing_criteria": self.missing_criteria,
            "llm_hypothesis_hs": self.llm_hypothesis_hs,
            "subposition_resolution": self.subposition_resolution,
            "rgi_applied": self.rgi_applied,
            "rgi_applied_records": self.rgi_applied_records,
            "rgi_not_applicable": self.rgi_not_applicable,
        }


def _hs_digit_count(hs_code: str | None) -> int:
    return len(re.sub(r"\D", "", str(hs_code or "")))


def _extract_product_name(source_text: str, description: str) -> str:
    from .classification_completeness import _extract_product_name_from_source

    if source_text:
        name = _extract_product_name_from_source(source_text)
        if name:
            return name
    if description:
        head = description.split(" — ")[0].split(" Composition")[0].strip()
        return head.split(".")[0].strip() or "Non precise"
    return "Non precise"


def _criteria_from_tec_trace(
    item: dict[str, Any],
    working_hs: str,
    source_text: str,
) -> list[CriterionDecision]:
    """Criteres issus de la trace TEC (libelles index), pas de types produit en dur."""
    resolution = item.get("subposition_resolution") if isinstance(item.get("subposition_resolution"), dict) else {}
    trace = resolution.get("criteria_trace")
    if not isinstance(trace, list) or not trace:
        trace = build_criteria_trace_from_tec(working_hs, source_text)

    criteria: list[CriterionDecision] = []
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "not_required")
        status_aliases = {
            "confirmed": "satisfied",
            "excluded": "not_required",
            "unverifiable": "missing",
        }
        status = status_aliases.get(status, status)
        if status not in {"not_required", "required", "satisfied", "missing"}:
            status = "not_required"
        criteria.append(
            CriterionDecision(
                criterion_id=str(entry.get("criterion_id") or entry.get("tec_reference") or ""),
                label=str(entry.get("label") or ""),
                status=status,  # type: ignore[arg-type]
                tec_reference=str(entry.get("tec_reference") or ""),
                detail=str(entry.get("detail") or ""),
            )
        )
    return criteria


def _collect_rgi_trace(item: dict[str, Any]) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    """Retourne (regles appliquees, enregistrements structures, regles non applicables)."""
    journal = item.get("rgi_journal") if isinstance(item.get("rgi_journal"), dict) else {}
    if journal.get("entries"):
        applied = list(journal.get("applied_rules") or [])
        applied_records = [
            {"rule": str(e.get("rule") or ""), "reason": str(e.get("reason") or "")}
            for e in journal.get("entries", [])
            if isinstance(e, dict) and e.get("status") == "applied" and e.get("reason")
        ]
        not_applicable = [
            {"rule": str(e.get("rule") or ""), "reason": str(e.get("reason") or "")}
            for e in journal.get("entries", [])
            if isinstance(e, dict) and e.get("status") == "not_applicable" and e.get("reason")
        ]
        return applied, applied_records, not_applicable

    applied: list[str] = []
    applied_records: list[dict[str, str]] = []
    not_applicable: list[dict[str, str]] = []

    pipeline = item.get("rgi_pipeline") if isinstance(item.get("rgi_pipeline"), dict) else {}
    for record in pipeline.get("applied_rules") or []:
        if isinstance(record, dict) and record.get("applied") and record.get("rule"):
            rule = str(record["rule"])
            reason = str(record.get("reason") or "").strip()
            if rule not in applied:
                applied.append(rule)
            if reason:
                applied_records.append({"rule": rule, "reason": reason})

    for record in pipeline.get("not_applied_rules") or []:
        if isinstance(record, dict) and not record.get("applied") and record.get("rule"):
            reason = str(record.get("reason") or "").strip()
            if reason:
                not_applicable.append(
                    {
                        "rule": str(record["rule"]),
                        "reason": reason,
                    }
                )

    rgi_3b = item.get("rgi_3b") if isinstance(item.get("rgi_3b"), dict) else {}
    if rgi_3b.get("applied") and "RGI 3 b" not in applied:
        applied.append("RGI 3 b")
        reason = str(rgi_3b.get("reason") or rgi_3b.get("applied_reason") or "").strip()
        if reason:
            applied_records.append({"rule": "RGI 3 b", "reason": reason})
    elif rgi_3b.get("not_applicable_reason"):
        not_applicable.append({"rule": "RGI 3 b", "reason": str(rgi_3b["not_applicable_reason"])})

    return applied, applied_records, not_applicable


def synthesize_decision_from_final_item(
    *,
    source_text: str,
    item: dict[str, Any],
) -> ClassificationDecision:
    """Synthetise la decision a partir de l'etat final de l'item (post-moteur TEC/coherence)."""
    description = str(item.get("description") or "")
    llm_hypothesis = str(item.get("hs_code_suggested") or "").strip()
    if not llm_hypothesis:
        resolution = item.get("subposition_resolution") if isinstance(item.get("subposition_resolution"), dict) else {}
        if resolution.get("matched_code") and resolution.get("status") != "confirmed":
            llm_hypothesis = str(resolution.get("matched_code") or "")

    working_hs = llm_hypothesis or str(item.get("hs_code") or "")
    criteria = _criteria_from_tec_trace(item, working_hs, source_text)

    resolution = item.get("subposition_resolution") if isinstance(item.get("subposition_resolution"), dict) else {}
    confirmed = (
        resolution.get("status") == "confirmed"
        or (
            not item.get("subposition_status")
            and str(item.get("classification_status") or "").lower() == "confirmee"
            and _hs_digit_count(item.get("hs_code")) >= 8
        )
    )

    hs_code = str(item.get("hs_code") or "")
    position = position_code_from_hs(hs_code)
    chapter = str(item.get("chapter") or position.replace(".", "")[:2]).strip()
    classification_status = str(item.get("classification_status") or "provisoire")
    subposition_status = str(item.get("subposition_status") or "") or None
    confidence = int(item.get("confidence") or 65)

    missing = list(item.get("missing_fields") or [])
    if isinstance(resolution.get("missing_criteria"), list):
        for field in resolution["missing_criteria"]:
            if str(field).strip() and str(field) not in missing:
                missing.append(str(field))

    rgi_applied, rgi_applied_records, rgi_not_applicable = _collect_rgi_trace(item)

    return ClassificationDecision(
        product_identified=_extract_product_name(source_text, description),
        position_code=position,
        hs_code=hs_code,
        chapter=chapter,
        classification_status=classification_status,
        subposition_status=subposition_status,
        confidence=confidence,
        criteria=criteria,
        missing_criteria=missing[:6],
        llm_hypothesis_hs=llm_hypothesis,
        subposition_resolution=resolution,
        rgi_applied=rgi_applied,
        rgi_applied_records=rgi_applied_records,
        rgi_not_applicable=rgi_not_applicable,
    )


def render_outputs_from_decision(item: dict[str, Any], source_text: str) -> ClassificationDecision:
    """Regenere justification et analyse a partir des decisions deja prises."""
    from .rgi.journal import attach_rgi_journal_to_item

    attach_rgi_journal_to_item(item)
    decision = synthesize_decision_from_final_item(source_text=source_text, item=item)
    item["classification_decision"] = decision.to_dict()
    item["justification"] = build_justification_from_decision(decision, item=item)
    item["classification_analysis"] = build_analysis_from_decision(
        decision,
        source_text=source_text,
        item=item,
    )
    return decision


def build_classification_decision(
    *,
    source_text: str,
    item: dict[str, Any],
) -> ClassificationDecision:
    """Construit la decision structuree a partir de la source et du referentiel TEC."""
    description = str(item.get("description") or "")
    llm_hypothesis = str(item.get("hs_code") or item.get("hs_code_suggested") or "").strip()
    working_hs = llm_hypothesis or str(item.get("hs_code") or "")

    subposition = resolve_subposition_from_tec(working_hs, source_text)
    criteria = [
        CriterionDecision(
            criterion_id=str(entry.get("criterion_id") or entry.get("tec_reference") or ""),
            label=str(entry.get("label") or ""),
            status=str(entry.get("status") or "not_required"),  # type: ignore[arg-type]
            tec_reference=str(entry.get("tec_reference") or ""),
            detail=str(entry.get("detail") or ""),
        )
        for entry in subposition.criteria_trace
        if isinstance(entry, dict)
    ]

    confirmed = subposition.status == "confirmed"
    position = position_code_from_hs(subposition.matched_code if confirmed else working_hs)
    chapter = str(item.get("chapter") or position.replace(".", "")[:2]).strip()

    if confirmed:
        hs_code = subposition.matched_code or working_hs
        subposition_status = None
        classification_status = "confirmee"
        confidence = subposition.confidence_cap
        missing = []
    else:
        hs_code = subposition.hs_code or position
        subposition_status = "a_determiner"
        classification_status = "provisoire"
        confidence = subposition.confidence_cap
        missing = list(subposition.missing_criteria)

    for criterion in criteria:
        if criterion.status == "missing":
            label = criterion.label
            if label not in missing:
                missing.append(label if not criterion.detail else f"{label} : {criterion.detail}")

    rgi_applied, rgi_applied_records, rgi_not_applicable = _collect_rgi_trace(item)

    return ClassificationDecision(
        product_identified=_extract_product_name(source_text, description),
        position_code=position,
        hs_code=hs_code,
        chapter=chapter,
        classification_status=classification_status,
        subposition_status=subposition_status,
        confidence=confidence,
        criteria=criteria,
        missing_criteria=missing[:6],
        llm_hypothesis_hs=llm_hypothesis,
        subposition_resolution=subposition.to_dict(),
        rgi_applied=rgi_applied,
        rgi_applied_records=rgi_applied_records,
        rgi_not_applicable=rgi_not_applicable,
    )


def _truncate_explanatory_note(text: str, max_len: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    if cleaned.rstrip().endswith(":") or len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len]
    for separator in (". ", "; ", " — "):
        idx = cut.rfind(separator)
        if idx >= int(max_len * 0.35):
            return cut[: idx + len(separator.strip())].strip()
    return cut.rstrip(" ,;:-") + "…"


def _pick_explanatory_note(chapter: str) -> str:
    notes = get_chapter_explanatory_notes(chapter)
    if not notes:
        return ""
    for note in notes:
        candidate = _truncate_explanatory_note(note)
        if candidate and not candidate.rstrip().endswith(":"):
            return candidate
    return _truncate_explanatory_note(notes[0])


def build_justification_from_decision(
    decision: ClassificationDecision,
    *,
    item: dict[str, Any] | None = None,
) -> str:
    """
    Reformule uniquement des decisions deja tracees dans le referentiel.
    Le journal RGI technique precede les elements TEC ; le LLM ne choisit pas les RGI.
    """
    parts: list[str] = []
    journal_text = str((item or {}).get("rgi_journal_text") or "").strip()
    if journal_text:
        parts.append(journal_text.replace("\n", " | "))

    resolution = decision.subposition_resolution or {}
    retained_code = decision.hs_code if _hs_digit_count(decision.hs_code) > 4 else decision.position_code
    retained_label = lookup_position_label(retained_code) or get_position_heading(decision.position_code) or ""

    if retained_label:
        parts.append(f"[TEC] Niveau retenu {retained_code} : {retained_label}.")
    else:
        parts.append(f"[TEC] Niveau retenu : {retained_code}.")

    if not journal_text:
        for record in decision.rgi_applied_records:
            rule = record.get("rule", "").strip()
            reason = record.get("reason", "").strip()
            if rule and reason:
                parts.append(f"[{rule}] {reason}")

        for entry in decision.rgi_not_applicable:
            rule = entry.get("rule", "").strip()
            reason = entry.get("reason", "").strip()
            if rule and reason:
                parts.append(f"[{rule}] Non applicable : {reason}.")

    confirmed = (
        decision.classification_status == "confirmee"
        and _hs_digit_count(decision.hs_code) >= 8
        and resolution.get("status") == "confirmed"
    )

    if confirmed:
        tec_label = lookup_position_label(decision.hs_code) or ""
        if tec_label:
            parts.append(f"[TEC] Sous-position {decision.hs_code} : {tec_label}.")
        explanation = str(resolution.get("explanation") or "").strip()
        if explanation:
            parts.append(f"[TEC] {explanation}")
        for criterion in decision.criteria:
            if criterion.status == "satisfied" and criterion.tec_reference:
                sub_label = lookup_position_label(criterion.tec_reference) or ""
                if sub_label and criterion.tec_reference != decision.hs_code:
                    parts.append(f"[TEC {criterion.tec_reference}] {sub_label}.")
    else:
        missing = [str(m).strip() for m in decision.missing_criteria if str(m).strip()]
        if missing:
            parts.append("[TEC] " + "; ".join(missing[:3]) + ".")
        else:
            parts.append("[TEC] Sous-position non determinable avec les informations disponibles.")
        parts.append(f"[TEC] Arret au niveau {retained_code}.")
        explanation = str(resolution.get("explanation") or "").strip()
        if explanation and explanation not in " ".join(parts):
            parts.append(f"[TEC] {explanation}")

    notes = _pick_explanatory_note(decision.chapter)
    if notes and decision.subposition_status == "a_determiner":
        parts.append(f"[Note explicative ch. {decision.chapter}] {notes}.")

    if decision.llm_hypothesis_hs and decision.llm_hypothesis_hs != decision.hs_code:
        hypo_position = position_code_from_hs(decision.llm_hypothesis_hs)
        parts.append(
            f"[Hypothese modele] Code suggere non retenu (position {hypo_position})."
        )

    return " ".join(parts)


def build_analysis_from_decision(
    decision: ClassificationDecision,
    *,
    source_text: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    """Construit l'analyse structuree a partir de la decision, sans parser le texte LLM."""
    from .classification_analysis import _extract_composition_lines, _extract_function

    position_code = decision.position_code
    chapter = decision.chapter
    description = str(item.get("description") or "")
    function = _extract_function(source_text, description)
    why_reasons: list[str] = []
    heading = get_position_heading(position_code) or str(item.get("position_label") or "").strip()
    if heading:
        why_reasons.append(f"[TEC] Position {position_code} : {heading}.")

    for record in decision.rgi_applied_records:
        rule = record.get("rule", "").strip()
        reason = record.get("reason", "").strip()
        if rule and reason:
            why_reasons.append(f"[{rule}] {reason}")

    resolution = decision.subposition_resolution or {}
    if decision.subposition_status == "a_determiner":
        missing = decision.missing_criteria
        if missing:
            why_reasons.append("[TEC] " + "; ".join(missing[:2]) + ".")
        else:
            why_reasons.append("[TEC] Sous-position non determinable avec les informations disponibles.")
    elif _hs_digit_count(decision.hs_code) >= 8:
        tec_label = lookup_position_label(decision.hs_code) or ""
        if tec_label:
            why_reasons.append(f"[TEC] Sous-position {decision.hs_code} : {tec_label}.")
        explanation = str(resolution.get("explanation") or "").strip()
        if explanation:
            why_reasons.append(f"[TEC] {explanation}")

    alternatives: list[dict[str, str]] = [
        {
            "code": position_code,
            "status": "retained",
            "reason": why_reasons[0] if why_reasons else f"[TEC] Position {position_code}.",
        }
    ]
    if decision.llm_hypothesis_hs and decision.llm_hypothesis_hs != decision.hs_code:
        alternatives.append(
            {
                "code": position_code_from_hs(decision.llm_hypothesis_hs),
                "status": "rejected",
                "reason": "[Hypothese modele] Code suggere non retenu par le referentiel TEC.",
            }
        )

    composition = _extract_composition_lines(source_text)
    facts = [f"Produit decrit par l'utilisateur : {decision.product_identified}"]
    if composition:
        facts.append("Composition declaree : " + ", ".join(composition))

    if decision.subposition_status == "a_determiner":
        decision_text = (
            f"[TEC] Position {position_code} retenue. "
            "Sous-position non determinable avec les informations disponibles."
        )
    else:
        decision_text = f"[TEC] Position {position_code} et sous-position {decision.hs_code} confirmees."

    return {
        "product_identified": decision.product_identified,
        "function": function,
        "composition_lines": composition,
        "chapters_studied": [chapter] if chapter else [],
        "chapter_retained": chapter,
        "chapter_name": get_full_chapter_name(chapter, str(item.get("chapter_name") or "")),
        "position_retained": position_code,
        "why_position": {
            "code": position_code,
            "title": f"Pourquoi {position_code} ?",
            "reasons": why_reasons or [f"[TEC] Position {position_code} retenue selon le referentiel."],
        },
        "alternatives_studied": alternatives,
        "explanatory_notes": [
            {"scope": f"Chapitre {chapter}", "text": note}
            for note in get_chapter_explanatory_notes(chapter)
        ],
        "missing_information": decision.missing_criteria,
        "criteria_decisions": [c.to_dict() for c in decision.criteria],
        "rgi_applied": decision.rgi_applied,
        "rgi_applied_records": decision.rgi_applied_records,
        "rgi_not_applicable": decision.rgi_not_applicable,
        "rgi_journal": item.get("rgi_journal") if isinstance(item.get("rgi_journal"), dict) else {},
        "rgi_journal_text": str(item.get("rgi_journal_text") or ""),
        "rgi_pipeline": item.get("rgi_pipeline") if isinstance(item.get("rgi_pipeline"), dict) else {},
        "decision": decision_text,
        "facts": facts,
        "hypotheses": (
            [f"[Hypothese modele] {decision.llm_hypothesis_hs}"]
            if decision.llm_hypothesis_hs and decision.llm_hypothesis_hs != decision.hs_code
            else []
        ),
        "confidence": decision.confidence,
    }


def apply_decision_engine_to_item(item: dict[str, Any], source_text: str) -> ClassificationDecision:
    """
    Execute le moteur de decision et propage ses resultats dans l'item.
    Le texte affiche (justification, analyse) est genere apres les decisions.
    """
    llm_hypothesis = str(item.get("hs_code") or "").strip()
    decision = build_classification_decision(source_text=source_text, item=item)

    item["classification_decision"] = decision.to_dict()
    item["hs_code"] = decision.hs_code
    item["classification_status"] = decision.classification_status
    item["confidence"] = decision.confidence
    item["missing_fields"] = decision.missing_criteria
    item["subposition_resolution"] = decision.subposition_resolution

    if decision.subposition_status:
        item["subposition_status"] = decision.subposition_status
        if decision.missing_criteria:
            item["subposition_label"] = f"Sous-position a determiner : {decision.missing_criteria[0]}"
    else:
        item.pop("subposition_status", None)
        item.pop("subposition_label", None)

    if llm_hypothesis and llm_hypothesis != decision.hs_code:
        item["hs_code_suggested"] = llm_hypothesis

    item["requires_exterior_surface"] = any(
        c.status == "missing" and "surface exterieure" in c.label.lower() for c in decision.criteria
    )

    label = lookup_position_label(decision.hs_code)
    if label:
        item["position_label"] = label
    elif decision.subposition_status:
        heading = get_position_heading(decision.position_code)
        if heading:
            item["position_label"] = heading

    item["justification"] = build_justification_from_decision(decision, item=item)
    item["classification_analysis"] = build_analysis_from_decision(
        decision,
        source_text=source_text,
        item=item,
    )
    return decision


def build_narrative_from_classifications(classifications: list[dict[str, Any]]) -> str:
    """
    Narrative utilisateur derivee des decisions structurees.
    Remplace le texte libre du modele : aucun code ni motif juridique invente.
    """
    from .brand_messaging import INDICATIVE_DISCLAIMER_ASCII
    from .classification_completeness import _resolve_product_label

    items = [item for item in classifications if isinstance(item, dict)]
    if not items:
        return INDICATIVE_DISCLAIMER_ASCII

    blocks: list[str] = [INDICATIVE_DISCLAIMER_ASCII]
    for item in items:
        source = str(item.get("source_query") or item.get("description") or "").strip()
        decision = synthesize_decision_from_final_item(source_text=source, item=item)
        from_label = _resolve_product_label(item)
        from_decision = decision.product_identified
        if from_label != "l'article":
            product = from_label
        elif from_decision and from_decision.lower() not in {"non precise"}:
            product = from_decision
        else:
            product = from_label
        journal_text = str(item.get("rgi_journal_text") or "").strip()
        body = build_justification_from_decision(decision, item=item)
        blocks.extend(["", "Produit analyse", product, ""])
        if journal_text:
            blocks.append(journal_text)
            blocks.append("")
        blocks.append(body)

    return "\n".join(blocks).strip()
