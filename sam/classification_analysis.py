"""Analyse structuree du raisonnement de classification."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .tariff_metadata import get_full_chapter_name, get_position_heading
from .tariff_notes import get_chapter_explanatory_notes

_MATERIAL_SHARE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*%\s*"
    r"(cuir|polyester|nylon|coton|textile|plastique|pvc|pu|polyurethane|polyurethan|"
    r"polypropylene|polyethylene|feutre|toile|lin|laine|soie|caoutchouc|aluminium|metal)",
    re.IGNORECASE | re.UNICODE,
)

_HS_CODE_RE = re.compile(r"\b(\d{4}\.\d{2}(?:\.\d{2}(?:\.\d{2})?)?)\b")
_CHAPTER_REF_RE = re.compile(r"(?:chapitre|ch\.?)\s*(\d{2})\b", re.IGNORECASE)
_REJECTION_RE = re.compile(
    r"ecarte|rejete|exclu|non retenu|non applicable|non assimila",
    re.IGNORECASE,
)
_RETENTION_RE = re.compile(
    r"retenu|retient|caractere essentiel|fonction principale|releve du",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _format_retained_position_code(hs_code: str | None) -> str:
    digits = re.sub(r"\D", "", str(hs_code or ""))
    if len(digits) >= 4:
        return f"{digits[:2]}.{digits[2:4]}"
    return str(hs_code or "").strip()


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _extract_product_name(source_text: str, description: str) -> str:
    if source_text:
        from .classification_completeness import _extract_product_name_from_source

        from_source = _extract_product_name_from_source(source_text)
        if from_source:
            return from_source
    for text in (source_text, description):
        match = re.search(
            r"(?im)^(?:produit|marchandise|article)\s*:\s*(.+)$",
            text or "",
        )
        if match:
            return match.group(1).strip()
    if description:
        head = description.split(" — ")[0].split(" Composition")[0].strip()
        return head.split(".")[0].strip()
    return "Non precise"


def _extract_composition_lines(source_text: str) -> list[str]:
    lines: list[str] = []
    for match in _MATERIAL_SHARE_RE.finditer(source_text or ""):
        lines.append(f"{match.group(1).strip()} % {match.group(2).strip()}")
    return lines


def _extract_rgi_tokens(justification: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"RGI\s*(\d+(?:\s*[a-z])?)", justification or "", re.IGNORECASE):
        token = f"RGI {match.group(1).strip().upper()}"
        if token not in tokens:
            tokens.append(token)
    return tokens


def _extract_function(source_text: str, description: str) -> str:
    for text in (source_text, description):
        match = re.search(r"(?im)^usage\s*:\s*(.+)$", text or "")
        if match:
            return match.group(1).strip()
    return "Non precise"


def _extract_chapters_from_text(text: str) -> list[str]:
    chapters = [match.group(1) for match in _CHAPTER_REF_RE.finditer(text or "")]
    return list(dict.fromkeys(chapters))


def _extract_chapters_studied(chapter: str, combined_text: str) -> list[str]:
    """Chapitres mentionnes dans le texte d'analyse (justification / narrative), sans liste fixe."""
    chapters = _extract_chapters_from_text(combined_text)
    if chapter and chapter not in chapters:
        chapters.insert(0, chapter)
    return chapters


def _position_digits(code: str) -> str:
    return re.sub(r"\D", "", code)[:4]


def _extract_rejection_snippets(
    justification: str,
    *,
    chapter: str,
    position_code: str,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    retained_digits = _position_digits(position_code)

    for sentence in _split_sentences(justification):
        if not _REJECTION_RE.search(sentence):
            continue
        for code in _HS_CODE_RE.findall(sentence):
            if _position_digits(code) == retained_digits:
                continue
            key = f"code:{code}"
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {"code": code, "status": "rejected", "reason": sentence[:240]}
            )
        for alt_ch in _extract_chapters_from_text(sentence):
            if alt_ch == chapter:
                continue
            key = f"ch:{alt_ch}"
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "code": f"Chapitre {alt_ch}",
                    "status": "rejected",
                    "reason": sentence[:240],
                }
            )
    return results


def _extract_retention_reasons(justification: str, narrative: str = "") -> list[str]:
    reasons: list[str] = []
    for sentence in _split_sentences(f"{justification}\n{narrative}"):
        if _REJECTION_RE.search(sentence):
            continue
        if _RETENTION_RE.search(sentence) or sentence.upper().startswith("RGI"):
            if sentence not in reasons:
                reasons.append(sentence[:240])
    return reasons[:4]


def _build_why_position(
    *,
    position_code: str,
    chapter: str,
    source_text: str,
    description: str,
    item: dict[str, Any],
    justification: str,
) -> dict[str, Any]:
    title = f"Pourquoi {position_code} ?"
    reasons: list[str] = []

    function = _extract_function(source_text, description)
    if function != "Non precise":
        reasons.append(f"Usage declare : {function.rstrip('.')}.")

    heading = get_position_heading(position_code) or str(item.get("position_label") or "").strip()
    if heading:
        reasons.append(f"Libelle TEC de la position {position_code} : {heading}.")
    else:
        chapter_name = get_full_chapter_name(chapter, str(item.get("chapter_name") or ""))
        if chapter_name:
            reasons.append(f"Chapitre {chapter} : {chapter_name}.")

    reasons.extend(_extract_retention_reasons(justification))

    if item.get("requires_exterior_surface") or item.get("subposition_status") == "a_determiner":
        reasons.append(
            "Seule la position est confirmee ; la sous-position depend des informations manquantes."
        )

    if not reasons:
        reasons.append("Voir la justification detaillee ci-dessous.")

    return {"code": position_code, "title": title, "reasons": reasons}


def _build_alternatives_studied(
    *,
    position_code: str,
    chapter: str,
    justification: str,
) -> list[dict[str, str]]:
    retention_reasons = _extract_retention_reasons(justification)
    retained_reason = retention_reasons[0] if retention_reasons else "Code retenu (voir justification)."
    alternatives: list[dict[str, str]] = [
        {
            "code": position_code,
            "status": "retained",
            "reason": retained_reason,
        }
    ]
    alternatives.extend(
        _extract_rejection_snippets(
            justification,
            chapter=chapter,
            position_code=position_code,
        )
    )
    return alternatives


def build_structured_classification_analysis(
    *,
    source_text: str | None,
    item: dict[str, Any],
    completeness: dict[str, Any],
) -> dict[str, Any]:
    description = str(item.get("description") or "")
    justification = str(item.get("justification") or "")
    chapter = str(item.get("chapter") or "").strip()
    combined = f"{source_text or ''}\n{description}\n{justification}"
    position_code = _format_retained_position_code(str(item.get("hs_code") or ""))

    rgi_applied = _extract_rgi_tokens(justification)
    rgi_3b_meta = item.get("rgi_3b") if isinstance(item.get("rgi_3b"), dict) else {}
    rgi_pipeline_meta = item.get("rgi_pipeline") if isinstance(item.get("rgi_pipeline"), dict) else {}
    rgi_not_applicable_early = None
    if rgi_3b_meta.get("applied"):
        if "RGI 3 b" not in rgi_applied and "RGI 3" not in rgi_applied:
            rgi_applied = ["RGI 3 b"] + [r for r in rgi_applied if not re.match(r"RGI\s*3", r, re.I)]
    elif rgi_3b_meta.get("not_applicable_reason"):
        rgi_not_applicable_early = {
            "rule": "RGI 3 b",
            "reason": str(rgi_3b_meta.get("not_applicable_reason") or ""),
        }

    rgi_not_applicable: list[dict[str, str]] = []
    if rgi_not_applicable_early:
        rgi_not_applicable.append(rgi_not_applicable_early)
    if completeness.get("requires_exterior_surface"):
        rgi_applied = [r for r in rgi_applied if not re.match(r"RGI\s*3", r, re.I)]
        if not rgi_applied:
            rgi_applied = ["RGI 1"]
        missing = completeness.get("missing_critical") or []
        missing_reason = missing[0] if missing else "information insuffisante pour la sous-position"
        rgi_not_applicable.append(
            {
                "rule": "RGI 3",
                "reason": f"Non applicable faute de : {missing_reason}",
            }
        )

    subposition_status = str(item.get("subposition_status") or "")
    if subposition_status == "a_determiner":
        decision = (
            f"Position {position_code} retenue. "
            "Sous-position a confirmer apres identification des informations manquantes."
        )
    else:
        decision = f"Position {position_code} retenue avec sous-position proposee."

    facts = [
        f"Produit decrit par l'utilisateur : {_extract_product_name(source_text or '', description)}",
    ]
    composition = _extract_composition_lines(source_text or "")
    if composition:
        facts.append("Composition declaree : " + ", ".join(composition))

    hypotheses: list[str] = []
    suggested = item.get("hs_code_suggested")
    if suggested and str(suggested) != str(item.get("hs_code") or ""):
        hypotheses.append(f"Hypothese initiale du modele : {suggested}")

    why_position = _build_why_position(
        position_code=position_code,
        chapter=chapter,
        source_text=source_text or "",
        description=description,
        item=item,
        justification=justification,
    )
    alternatives_studied = _build_alternatives_studied(
        position_code=position_code,
        chapter=chapter,
        justification=justification,
    )
    explanatory_notes = [
        {"scope": f"Chapitre {chapter}", "text": note}
        for note in get_chapter_explanatory_notes(chapter)
    ]

    return {
        "product_identified": _extract_product_name(source_text or "", description),
        "function": _extract_function(source_text or "", description),
        "composition_lines": composition,
        "chapters_studied": _extract_chapters_studied(chapter, combined),
        "chapter_retained": chapter,
        "chapter_name": get_full_chapter_name(chapter, str(item.get("chapter_name") or "")),
        "position_retained": position_code,
        "why_position": why_position,
        "alternatives_studied": alternatives_studied,
        "explanatory_notes": explanatory_notes,
        "missing_information": completeness.get("missing_critical", []),
        "rgi_applied": [r for r in rgi_applied if r not in {x["rule"] for x in rgi_not_applicable}],
        "rgi_not_applicable": rgi_not_applicable,
        "rgi_3b": rgi_3b_meta,
        "rgi_pipeline": rgi_pipeline_meta,
        "decision": decision,
        "facts": facts,
        "hypotheses": hypotheses,
        "confidence": item.get("confidence"),
    }
