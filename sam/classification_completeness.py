"""Analyse de completude avant/apres classification (informations indispensables manquantes)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .brand_messaging import INDICATIVE_DISCLAIMER_ASCII

from .tariff_labels import get_tariff_label_index
from .tariff_metadata import get_position_heading
from .tariff_notes import get_chapter_explanatory_notes
from .tariff_position_rules import is_subposition_sensitive_position, position_code_from_hs

_EXTERIOR_SURFACE_KEYWORDS = (
    "surface exterieure",
    "exterieur en",
    "exterieure en",
    "recouvert",
    "revetement",
    "revetement exterieur",
    "apparent",
    "face exterieure",
    "exterior",
    "couverture exterieure",
)

_MATERIAL_SHARE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*%\s*"
    r"(cuir|polyester|nylon|coton|textile|plastique|pvc|pu|polyurethane|polyurethan|"
    r"polypropylene|polyethylene|feutre|toile|lin|laine|soie|caoutchouc|aluminium|metal)",
    re.IGNORECASE | re.UNICODE,
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _has_definitive_exterior_surface(text: str) -> bool:
    """
    True seulement si la source utilisateur precise clairement la surface exterieure.
    Ignore les formulations vagues du type « surface mixte polyester et cuir ».
    """
    norm = _normalize(text)
    if not norm:
        return False
    if re.search(r"surface\s+exterieure\s*:", norm):
        return True
    if re.search(
        r"\b(?:exterieur|exterieure|surface)\s*:\s*(?:100\s*%|entiere(?:ment)?\s+en)\s+"
        r"(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
        norm,
    ):
        return True
    if re.search(
        r"\b(?:100\s*%|entiere(?:ment)?)\s+(?:en\s+)?(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\s+"
        r"(?:apparent|exterieur|exterieure)\b",
        norm,
    ):
        return True
    if re.search(
        r"\b(?:exterieur|exterieure)\s+(?:en|100\s*%)\s+(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
        norm,
    ):
        if "mixte" in norm or re.search(r"\bet\s+(?:cuir|textile|polyester|nylon)\b", norm):
            return False
        return True
    return False


def _has_exterior_surface_info(text: str) -> bool:
    norm = _normalize(text)
    if any(keyword in norm for keyword in _EXTERIOR_SURFACE_KEYWORDS):
        return True
    if re.search(
        r"\b(?:exterieur|exterieure|surface)\b.{0,40}\b(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\b",
        norm,
    ):
        return True
    if re.search(
        r"\b(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\b.{0,40}\b(?:exterieur|exterieure|apparent)\b",
        norm,
    ):
        return True
    return False


def _significant_materials(text: str) -> set[str]:
    materials: set[str] = set()
    for match in _MATERIAL_SHARE_RE.finditer(text):
        try:
            share = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if share >= 10:
            materials.add(_normalize(match.group(2)))
    return materials


def _is_mixed_composition(text: str) -> bool:
    materials = _significant_materials(text)
    textile_like = {"polyester", "nylon", "coton", "textile", "toile", "lin", "laine", "soie", "feutre"}
    leather_like = {"cuir", "pu", "polyurethane", "polyurethan"}
    has_textile = bool(materials & textile_like)
    has_leather = bool(materials & leather_like)
    has_plastic = bool(materials & {"plastique", "pvc", "polypropylene", "polyethylene"})
    kinds = sum([has_textile, has_leather, has_plastic])
    return kinds >= 2 or len(materials) >= 2


def _position_requires_subposition_detail(hs_code: str, chapter: str) -> bool:
    """Detecte via l'index TEC si la position exige un critere de sous-position (ex. surface exterieure)."""
    if is_subposition_sensitive_position(hs_code):
        return True
    position = position_code_from_hs(hs_code)
    heading = get_position_heading(position)
    if heading and "surface exterieure" in _normalize(heading):
        return True
    try:
        ch = int(str(chapter).lstrip("0") or "0")
    except ValueError:
        ch = 0
    for note in get_chapter_explanatory_notes(ch):
        if "surface exterieure" in _normalize(note):
            return True
    return False


def _tec_labels_for_position(hs_code: str) -> list[str]:
    position = position_code_from_hs(hs_code)
    prefix = position.replace(".", "")
    labels: list[str] = []
    for code, label in get_tariff_label_index().items():
        digits = re.sub(r"\D", "", code)
        if digits.startswith(prefix):
            labels.append(label)
    return labels


def _infer_missing_subposition_field(hs_code: str, chapter: str) -> str:
    position = position_code_from_hs(hs_code)
    heading = get_position_heading(position)
    if heading and "surface exterieure" in _normalize(heading):
        return "Surface exterieure (matiere apparente, selon libelle TEC)"
    for label in _tec_labels_for_position(hs_code):
        if "surface exterieure" in _normalize(label):
            return "Surface exterieure (matiere apparente, selon nomenclature TEC)"
    try:
        ch = int(str(chapter).lstrip("0") or "0")
    except ValueError:
        ch = 0
    for note in get_chapter_explanatory_notes(ch):
        if "surface exterieure" in _normalize(note):
            return "Surface exterieure (selon notes du chapitre TEC)"
    if is_subposition_sensitive_position(hs_code):
        return "Surface exterieure (matiere apparente, selon nomenclature TEC)"
    return "Information complementaire requise pour la sous-position (voir TEC)"


def analyze_classification_completeness(
    *,
    source_text: str | None = None,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = item or {}
    source_block = (source_text or "").strip()
    combined = "\n".join(
        part
        for part in (
            source_block,
            str(item.get("description") or ""),
            str(item.get("justification") or ""),
        )
        if part
    )
    norm = _normalize(combined)
    source_norm = _normalize(source_block)
    hs_code = str(item.get("hs_code") or "")
    chapter = str(item.get("chapter") or "").strip()

    has_function = any(
        token in (source_norm or norm)
        for token in ("usage", "transport", "destine", "fonction", "servant a", "pour le transport")
    )
    has_dimensions = bool(
        re.search(r"\d+\s*(?:l|litres?|cm|mm)\b", source_norm or norm)
        or re.search(r"\d+\s*[x×]\s*\d+", source_norm or norm)
        or "capacite" in (source_norm or norm)
        or "dimension" in (source_norm or norm)
    )
    has_composition = "composition" in (source_norm or norm) or bool(
        _significant_materials(source_block or combined)
    )
    has_origin = "origine" in (source_norm or norm) or "provenant" in (source_norm or norm)
    has_value = bool(
        re.search(r"\b(?:valeur|prix|usd|dollars?|eur|fcfa)\b", source_norm or norm)
    )
    has_exterior = _has_definitive_exterior_surface(source_block)
    has_revetement = any(
        token in (source_norm or norm)
        for token in ("revetement", "recouvert", "doublure", "interieur")
    )
    has_brand = any(token in (source_norm or norm) for token in ("marque", "brand", "fabricant"))

    subposition_detail_required = _position_requires_subposition_detail(hs_code, chapter)
    mixed = _is_mixed_composition(source_block or combined)

    checklist: list[dict[str, str]] = [
        {"field": "function", "label": "Fonction / usage", "status": "ok" if has_function else "missing"},
        {"field": "composition", "label": "Composition", "status": "ok" if has_composition else "missing"},
        {
            "field": "dimensions",
            "label": "Dimensions / capacite",
            "status": "ok" if has_dimensions else "optional_missing",
        },
        {"field": "origin", "label": "Pays d'origine", "status": "ok" if has_origin else "optional_missing"},
        {"field": "value", "label": "Valeur", "status": "ok" if has_value else "optional_missing"},
        {
            "field": "brand",
            "label": "Marque",
            "status": "ok" if has_brand else "optional_missing",
        },
    ]

    missing_critical: list[str] = []
    missing_optional: list[str] = []

    if subposition_detail_required:
        exterior_status = "ok" if has_exterior else ("missing" if mixed else "optional_missing")
        checklist.append(
            {"field": "exterior_surface", "label": "Surface exterieure", "status": exterior_status}
        )
        if mixed and not has_exterior:
            missing_critical.append(_infer_missing_subposition_field(hs_code, chapter))
            missing_optional.append("Presence eventuelle d'un revetement")
            missing_optional.append("Cuir apparent ou textile apparent")
        checklist.append(
            {
                "field": "revetement",
                "label": "Revetement / doublure",
                "status": "ok" if has_revetement else "optional_missing",
            }
        )

    if not has_function and subposition_detail_required:
        missing_optional.append("Usage / fonction principale")

    score = 40
    if has_function:
        score += 15
    if has_composition:
        score += 20
    if has_dimensions:
        score += 10
    if has_exterior:
        score += 20
    elif subposition_detail_required and mixed:
        score -= 10
    if has_origin:
        score += 5
    if has_value:
        score += 5
    completeness_score = max(0, min(100, score))

    llm_status = str(item.get("classification_status") or "").strip().lower()
    can_confirm = not missing_critical
    if llm_status == "provisoire" and missing_critical:
        status = "provisoire"
    elif llm_status == "confirmee" and can_confirm:
        status = "confirmee"
    else:
        status = "confirmee" if can_confirm else "provisoire"

    requires_exterior_surface = bool(subposition_detail_required and mixed and not has_exterior)

    return {
        "checklist": checklist,
        "missing_critical": missing_critical,
        "missing_optional": [field for field in missing_optional if field not in missing_critical],
        "missing_fields": missing_critical + missing_optional,
        "completeness_score": completeness_score,
        "classification_status": status,
        "can_classify_confidently": can_confirm,
        "requires_exterior_surface": requires_exterior_surface,
        "subposition_detail_required": subposition_detail_required,
    }


def _subposition_code_pattern(position: str) -> re.Pattern[str]:
    prefix = position.replace(".", "")
    dotted = re.escape(position)
    return re.compile(
        rf"\b(?:{dotted}|{re.escape(prefix)})\.\d+(?:\.\d+)*\b",
        re.IGNORECASE,
    )


def _apply_provisional_position_level(item: dict[str, Any], analysis: dict[str, Any]) -> None:
    """Si la sous-position n'est pas confirmable, ne garder que la position."""
    hs = str(item.get("hs_code") or "").strip()
    digits = re.sub(r"\D", "", hs)
    if len(digits) <= 4:
        return
    position = position_code_from_hs(hs)
    item["hs_code_suggested"] = hs
    item["hs_code"] = position
    item["subposition_status"] = "a_determiner"
    missing = analysis.get("missing_critical") or []
    if missing:
        item["subposition_label"] = f"Sous-position a determiner : {missing[0]}"
    else:
        item["subposition_label"] = (
            "Sous-position a determiner apres validation des informations manquantes"
        )
    heading = get_position_heading(position)
    if heading:
        item["position_label"] = heading

    justification = str(item.get("justification") or "")
    justification = _subposition_code_pattern(position).sub(position, justification)
    item["justification"] = justification.strip()


_EXTERIOR_HALLUCINATION_RE = re.compile(
    r"(?:,\s*|\bavec\s+)?surface\s+exterieure\s+mixte\b[^,;.]",
    re.IGNORECASE,
)
_EXTERIOR_MATERIAL_CLAIM_RE = re.compile(
    r"(?:,\s*|\bavec\s+)surface\s+exterieure\s+(?:en\s+)?(?:cuir|textile|polyester|nylon|plastique|pvc|toile)\b[^,;.]",
    re.IGNORECASE,
)
_RGI3_APPLIED_CLAUSE_RE = re.compile(
    r"RGI\s*3\s*[a-z]?\s*(?:appliquee?s?|applique|applicable)\s*[^.!?]*[.!?]?",
    re.IGNORECASE,
)
_SURFACE_MIXTE_CLAUSE_RE = re.compile(
    r"[^.!?]*surface\s+exterieure\s+mixte[^.!?]*[.!?]?",
    re.IGNORECASE,
)
_PROPOSITION_BOILERPLATE_RE = re.compile(
    r"Proposition indicative[^.!?]*[.!?]\s*",
    re.IGNORECASE,
)


def _expand_dossier_sections(text: str) -> str:
    """Reformate une fiche sur une seule ligne en sections multi-lignes."""
    if not text or "\n" in text:
        return text
    expanded = text
    for section in ("Composition", "Usage", "Capacite", "Caracteristiques", "Origine", "Valeur"):
        expanded = re.sub(rf"\s+({section}\s*:)", r"\n\1", expanded, flags=re.IGNORECASE)
    return expanded


def _truncate_product_label(text: str) -> str:
    """Garde uniquement le nom court du produit (sans composition / usage / capacite)."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    inline = re.search(
        r"(?i)(?:produit|marchandise|article)\s*:\s*"
        r"(.+?)(?:\s+composition\s*:|\s+usage\s*:|\s+capacite\s*:|$)",
        cleaned,
    )
    if inline:
        return inline.group(1).strip().rstrip(".")
    lowered = cleaned.lower()
    for marker in (" composition", " usage", " capacite", " — composition"):
        pos = lowered.find(marker)
        if pos > 0:
            return cleaned[:pos].strip().rstrip(".")
    if " — " in cleaned:
        return cleaned.split(" — ", 1)[0].strip()
    return cleaned.split(".", 1)[0].strip()


def _append_materials_from_line(line: str, dossier: dict[str, Any]) -> bool:
    found = False
    for match in _MATERIAL_SHARE_RE.finditer(line):
        found = True
        dossier["composition"].append(
            f"{match.group(1).strip()} % {match.group(2).strip()}"
        )
    return found


def _parse_product_dossier(source_text: str) -> dict[str, Any]:
    """Extrait produit, composition, usage et capacite d'une fiche structuree."""
    dossier: dict[str, Any] = {
        "product": "",
        "composition": [],
        "usage": "",
        "capacity": "",
    }
    normalized_text = _expand_dossier_sections(source_text or "")
    in_composition = False
    for raw_line in normalized_text.splitlines():
        line = raw_line.strip().lstrip("- ").strip()
        if not line:
            if in_composition and dossier["composition"]:
                in_composition = False
            continue
        norm = _normalize(line)
        if norm.startswith("produit") and ":" in line:
            dossier["product"] = _truncate_product_label(line.split(":", 1)[1])
            in_composition = False
        elif norm.startswith("composition"):
            in_composition = True
            _append_materials_from_line(line, dossier)
        elif in_composition:
            if _append_materials_from_line(line, dossier):
                continue
            match = _MATERIAL_SHARE_RE.search(line)
            if match:
                dossier["composition"].append(
                    f"{match.group(1).strip()} % {match.group(2).strip()}"
                )
            elif dossier["composition"]:
                in_composition = False
        elif norm.startswith("usage") and ":" in line:
            dossier["usage"] = line.split(":", 1)[1].strip().rstrip(".")
        elif ("capacite" in norm or re.search(r"\d+\s*litres?", norm)) and ":" in line:
            dossier["capacity"] = line.split(":", 1)[1].strip().rstrip(".")
        elif re.search(r"\d+\s*litres?", norm) and not dossier["capacity"]:
            dossier["capacity"] = line.strip().rstrip(".")
    return dossier


def _format_dossier_description(dossier: dict[str, Any]) -> str:
    """Libelle marchandise concis pour le tableau (sans repeter toute la fiche)."""
    segments: list[str] = []
    product = str(dossier.get("product") or "").strip()
    if product:
        segments.append(product)
    composition = dossier.get("composition") or []
    if composition:
        segments.append("composition mixte (" + ", ".join(composition) + ")")
    usage = str(dossier.get("usage") or "").strip()
    if usage:
        segments.append(usage)
    capacity = str(dossier.get("capacity") or "").strip()
    if capacity:
        segments.append(f"capacite {capacity}")
    return " — ".join(segments)


def _extract_product_name_from_source(source_text: str) -> str:
    dossier = _parse_product_dossier(source_text)
    product = str(dossier.get("product") or "").strip()
    if product:
        return _truncate_product_label(product)
    return _truncate_product_label(source_text)


def _resolve_product_label(item: dict[str, Any]) -> str:
    for candidate in (
        item.get("product_name"),
        _extract_product_name_from_source(str(item.get("source_query") or "")),
        _extract_product_name_from_source(str(item.get("description") or "")),
        _truncate_product_label(str(item.get("description") or "")),
        item.get("classification_analysis", {}).get("product_identified"),
    ):
        short = _truncate_product_label(str(candidate or ""))
        if short and short.lower() not in {"non precise", "l'article"}:
            return short
    return "l'article"


def _rebuild_description_from_source(source_text: str) -> str:
    """Reconstruit une description fiable et concise a partir de la fiche utilisateur."""
    dossier = _parse_product_dossier(source_text)
    formatted = _format_dossier_description(dossier)
    if formatted:
        return formatted
    for raw_line in (source_text or "").splitlines():
        line = raw_line.strip()
        if line and not _normalize(line).startswith("composition"):
            return line
    return ""


def build_provisional_ch42_narrative(classifications: list[dict[str, Any]]) -> str:
    product_label = "l'article"
    position_code = "la position retenue"
    chapter = ""
    for item in classifications:
        if not isinstance(item, dict) or not item.get("requires_exterior_surface"):
            continue
        product_label = _resolve_product_label(item)
        hs = str(item.get("hs_code") or "").strip()
        if hs:
            digits = re.sub(r"\D", "", hs)
            if len(digits) >= 4:
                position_code = f"{digits[:2]}.{digits[2:4]}"
            else:
                position_code = hs
        chapter = str(item.get("chapter") or "").strip()
        break
    chapter_part = f"du chapitre {chapter}" if chapter else "du chapitre concerne"
    return (
        f"{INDICATIVE_DISCLAIMER_ASCII}\n\n"
        "Produit analyse\n"
        f"{product_label}\n\n"
        "La matiere de la surface exterieure n'est pas precisee dans la description fournie. "
        "Les pourcentages de composition globale ne suffisent pas a determiner la sous-position "
        f"{chapter_part}. Position retenue : {position_code}, sous-position a confirmer. "
        "RGI 1 appliquee. RGI 3 non applicable faute d'information suffisante."
    )


def sanitize_provisional_narrative(narrative: str, classifications: list[dict[str, Any]]) -> str:
    """Nettoie le narrative global : texte canonique provisoire, sinon dedoublonnage."""
    needs_provisional_narrative = any(
        isinstance(item, dict) and item.get("requires_exterior_surface")
        for item in classifications
    )
    if needs_provisional_narrative:
        return build_provisional_ch42_narrative(classifications)

    text = (narrative or "").strip()
    if not text:
        return text

    body = _PROPOSITION_BOILERPLATE_RE.sub("", text).strip()
    body = re.sub(r"\s{2,}", " ", body).strip()
    prefix = f"{INDICATIVE_DISCLAIMER_ASCII}"
    return f"{prefix} {body}".strip() if body else prefix


def _strip_llm_exterior_hallucinations(text: str) -> str:
    cleaned = _EXTERIOR_HALLUCINATION_RE.sub("", text or "")
    cleaned = _EXTERIOR_MATERIAL_CLAIM_RE.sub("", cleaned)
    cleaned = _SURFACE_MIXTE_CLAUSE_RE.sub("", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;.")
    return cleaned


def _strip_false_rgi3_claims(text: str) -> str:
    cleaned = _RGI3_APPLIED_CLAUSE_RE.sub("", text or "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _sanitize_provisional_item_text(
    item: dict[str, Any],
    source_text: str | None = None,
    *,
    analysis: dict[str, Any] | None = None,
) -> None:
    """Retire les affirmations inventees (surface exterieure, RGI 3) quand l'info manque."""
    source_block = (source_text or str(item.get("description") or "")).strip()
    if _has_definitive_exterior_surface(source_block):
        return

    rebuilt = _rebuild_description_from_source(source_block)
    if rebuilt:
        item["description"] = rebuilt
        item["product_name"] = _extract_product_name_from_source(source_block) or _truncate_product_label(
            rebuilt.split(" — ", 1)[0]
        )
    else:
        description = str(item.get("description") or "")
        if description and (
            "surface exterieure" in _normalize(description)
            or "surface mixte" in _normalize(description)
        ):
            item["description"] = _strip_llm_exterior_hallucinations(description)

    justification = str(item.get("justification") or "")
    justification = _strip_false_rgi3_claims(justification)
    missing = (analysis or {}).get("missing_critical") or []
    if missing:
        rgi3_note = (
            "RGI 3 non applicable : information insuffisante pour appliquer un critere de sous-position "
            f"({'; '.join(missing)})."
        )
        if rgi3_note.lower() not in justification.lower():
            justification = f"{justification} {rgi3_note}".strip()
    item["justification"] = justification


def apply_completeness_adjustments(item: dict[str, Any], source_text: str | None = None) -> None:
    """Enrichit la classification et ajuste confiance/statut si informations critiques manquent."""
    analysis = analyze_classification_completeness(source_text=source_text, item=item)
    item["completeness_checklist"] = analysis["checklist"]
    item["missing_fields"] = analysis["missing_fields"]
    item["completeness_score"] = analysis["completeness_score"]
    item["classification_status"] = analysis["classification_status"]
    item["requires_exterior_surface"] = analysis["requires_exterior_surface"]
    item["subposition_detail_required"] = analysis["subposition_detail_required"]

    if not analysis["can_classify_confidently"]:
        confidence = item.get("confidence")
        try:
            current_conf = int(round(float(confidence)))
        except (TypeError, ValueError):
            current_conf = 90
        item["confidence"] = min(current_conf, 65)

        justification = str(item.get("justification") or "").strip()
        if analysis["missing_critical"]:
            note = (
                "Information insuffisante pour determiner avec certitude la sous-position : "
                + "; ".join(analysis["missing_critical"])
            )
            if note.lower() not in justification.lower():
                item["justification"] = f"{justification} {note}".strip() if justification else note

        hs_digits = re.sub(r"\D", "", str(item.get("hs_code") or ""))
        if analysis["requires_exterior_surface"] or (
            analysis["subposition_detail_required"] and len(hs_digits) > 4
        ):
            _apply_provisional_position_level(item, analysis)
            _sanitize_provisional_item_text(item, source_text=source_text, analysis=analysis)

    from .classification_analysis import build_structured_classification_analysis

    item["classification_analysis"] = build_structured_classification_analysis(
        source_text=source_text,
        item=item,
        completeness=analysis,
    )

    if item.get("description_quality") is not None and analysis["requires_exterior_surface"]:
        try:
            item["description_quality"] = min(int(item["description_quality"]), 78)
        except (TypeError, ValueError):
            item["description_quality"] = 78
