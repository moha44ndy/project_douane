"""Analyse de completude avant/apres classification (informations indispensables manquantes)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .brand_messaging import INDICATIVE_DISCLAIMER_ASCII

from .tariff_labels import get_tariff_label_index, lookup_position_label
from .tariff_metadata import get_position_heading
from .tariff_position_rules import position_code_from_hs
from .tariff_subposition import (
    position_has_discriminating_subpositions,
    preview_missing_discriminating_criteria,
)
from .classification_source import build_effective_classification_source
from .product_identification import looks_like_structured_dossier

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


_COMMERCIAL_VALUE_HINT = re.compile(
    r"\b(?:valeur|prix|usd|dollars?|eur|euros?|fcfa|xof|xaf|gbp|chf|cny|jpy|mad|ngn|ghs)\b",
    re.IGNORECASE,
)


def _is_commercial_field_unset(value: Any) -> bool:
    normalized = _normalize(str(value or "").strip())
    return not normalized or "non renseign" in normalized


def extract_commercial_fields_from_source(source_text: str) -> dict[str, str]:
    """Extrait origine et valeur depuis une fiche structuree ou une ligne inline."""
    result = {"origin": "", "value": ""}
    text = (source_text or "").replace("\r", "\n").strip()
    if not text:
        return result

    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        norm = _normalize(line)
        if norm.startswith("origine") and ":" in line:
            current = "origin"
            inline = line.split(":", 1)[1].strip()
            if inline:
                result["origin"] = inline
                current = None
            continue
        if norm.startswith("valeur") and ":" in line:
            current = "value"
            inline = line.split(":", 1)[1].strip()
            if inline:
                result["value"] = inline
                current = None
            continue
        if current == "origin":
            result["origin"] = line
            current = None
        elif current == "value":
            result["value"] = line
            current = None

    if not result["origin"]:
        match = re.search(
            r"(?i)\b(?:origine|provenant\s+de|pays\s+d['\u2019]?origine)\s*[:=]?\s*([^,\n;|]+)",
            text,
        )
        if match:
            result["origin"] = match.group(1).strip()
    if not result["value"]:
        match = re.search(
            r"(?i)\b(?:valeur|prix|montant)\s*[:=]?\s*([\d\s.,]+(?:\s*(?:usd|eur|euros?|fcfa|xof|xaf|gbp|chf))?)",
            text,
        )
        if match:
            result["value"] = match.group(1).strip()
    return result


def backfill_commercial_fields_from_source(item: dict[str, Any], source_text: str | None = None) -> None:
    """Reinjecte origine/valeur saisies par l'utilisateur si le LLM renvoie « Non renseigne »."""
    source = (source_text or item.get("source_query") or item.get("description") or "").strip()
    if not source:
        return
    fields = extract_commercial_fields_from_source(source)
    if _is_commercial_field_unset(item.get("origin")) and fields.get("origin"):
        item["origin"] = fields["origin"]
    if _is_commercial_field_unset(item.get("value")) and fields.get("value"):
        item["value"] = fields["value"]


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


def _tec_labels_for_position(hs_code: str) -> list[str]:
    position = position_code_from_hs(hs_code)
    prefix = position.replace(".", "")
    labels: list[str] = []
    for code, label in get_tariff_label_index().items():
        digits = re.sub(r"\D", "", code)
        if digits.startswith(prefix):
            labels.append(label)
    return labels


def _tec_position_mentions_surface(hs_code: str) -> bool:
    for label in _tec_labels_for_position(hs_code):
        if "surface exterieure" in _normalize(label):
            return True
    position = position_code_from_hs(hs_code)
    heading = get_position_heading(position)
    return bool(heading and "surface exterieure" in _normalize(heading))


def _hs_digit_count(hs_code: str) -> int:
    return len(re.sub(r"\D", "", str(hs_code or "")))


def _prepare_item_for_criteria_reevaluation(
    item: dict[str, Any],
    source_text: str | None,
) -> str:
    """
    Reévalue la description courante sans hériter d'un blocage antérieur.
    Si un code plus précis était suggéré et que les critères TEC sont désormais satisfaits,
    reprend la résolution à ce niveau.
    """
    for key in ("subposition_status", "subposition_label", "subposition_resolution"):
        item.pop(key, None)

    hs = str(item.get("hs_code") or "").strip()
    suggested = str(item.get("hs_code_suggested") or "").strip()
    source = (source_text or item.get("source_query") or item.get("description") or "").strip()

    if suggested and _hs_digit_count(suggested) > _hs_digit_count(hs) and source:
        from .tariff_subposition import resolve_subposition_from_tec

        preview = resolve_subposition_from_tec(suggested, source)
        if preview.status == "confirmed":
            item["hs_code"] = preview.matched_code or suggested
            return item["hs_code"]
        item["hs_code"] = suggested
        return suggested
    return hs


def analyze_classification_completeness(
    *,
    source_text: str | None = None,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Analyse les informations disponibles pour la description courante uniquement.
    Les critères manquants d'une classification antérieure ne bloquent pas si la
    description actuelle les fournit désormais.
    """
    item = item or {}
    source_block = (source_text or "").strip()
    effective_source, _trusted = build_effective_classification_source(source_block, item)
    combined = "\n".join(
        part
        for part in (
            effective_source,
            str(item.get("description") or ""),
            str(item.get("justification") or ""),
        )
        if part
    )
    norm = _normalize(combined)
    source_norm = _normalize(effective_source)
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
    has_value = bool(_COMMERCIAL_VALUE_HINT.search(source_norm or norm))
    has_exterior = _has_definitive_exterior_surface(effective_source or source_block)
    has_revetement = any(
        token in (source_norm or norm)
        for token in ("revetement", "recouvert", "doublure", "interieur")
    )
    has_brand = any(token in (source_norm or norm) for token in ("marque", "brand", "fabricant"))

    subposition_detail_required = position_has_discriminating_subpositions(hs_code)
    mixed = _is_mixed_composition(source_block or combined)
    tec_missing = preview_missing_discriminating_criteria(hs_code, effective_source, item) if hs_code else []

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

    missing_critical: list[str] = list(tec_missing)
    missing_optional: list[str] = []

    if subposition_detail_required and _tec_position_mentions_surface(hs_code):
        exterior_status = "ok" if has_exterior else ("missing" if "surface exterieure" in _normalize(" ".join(tec_missing)) else "optional_missing")
        checklist.append(
            {"field": "exterior_surface", "label": "Surface exterieure", "status": exterior_status}
        )
        checklist.append(
            {
                "field": "revetement",
                "label": "Revetement / doublure",
                "status": "ok" if has_revetement else "optional_missing",
            }
        )
    elif has_revetement:
        checklist.append(
            {
                "field": "revetement",
                "label": "Revetement / doublure",
                "status": "ok",
            }
        )

    score = 40
    if has_function:
        score += 15
    if has_composition:
        score += 20
    if has_dimensions:
        score += 10
    if has_exterior:
        score += 20
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

    requires_exterior_surface = any(
        "surface exterieure" in _normalize(field) for field in missing_critical
    )

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
    """Si la sous-position n'est pas confirmable, garder le dernier niveau TEC justifiable."""
    resolution = item.get("subposition_resolution")
    if isinstance(resolution, dict) and resolution.get("hs_code"):
        justified = str(resolution["hs_code"]).strip()
    else:
        justified = position_code_from_hs(str(item.get("hs_code") or ""))

    current = str(item.get("hs_code") or "").strip()
    current_digits = len(re.sub(r"\D", "", current))
    justified_digits = len(re.sub(r"\D", "", justified))
    if current_digits > justified_digits and justified_digits >= 4:
        item.setdefault("hs_code_suggested", current)
    item["hs_code"] = justified
    item["subposition_status"] = "a_determiner"
    missing = analysis.get("missing_critical") or []
    if missing:
        item["subposition_label"] = f"Sous-position a determiner : {missing[0]}"
    else:
        item["subposition_label"] = (
            "Sous-position a determiner apres validation des informations manquantes"
        )
    label = lookup_position_label(justified) or get_position_heading(position_code_from_hs(justified))
    if label:
        item["position_label"] = label


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
_INCOMPLETE_NARRATIVE_TAIL_RE = re.compile(
    r"\s+(?:cette classification est indicative et|proposition indicative et|"
    r"doit etre validee et|a faire valider et)\s*$",
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
    # Split only on sentence punctuation. Decimal capacities/model identifiers
    # such as 3.84TB must remain intact.
    return re.split(r"\.(?=\s|$)", cleaned, maxsplit=1)[0].strip().rstrip(".")


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
    source_query = str(item.get("source_query") or "")
    candidates: list[Any] = []
    if looks_like_structured_dossier(source_query):
        candidates.append(_extract_product_name_from_source(source_query))
    candidates.extend(
        [
            item.get("product_name"),
            _extract_product_name_from_source(source_query),
            _extract_product_name_from_source(str(item.get("description") or "")),
            _truncate_product_label(str(item.get("description") or "")),
            item.get("classification_analysis", {}).get("product_identified"),
        ]
    )
    for candidate in candidates:
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
    """Alias retro-compatible : narrative derivee du moteur de decision."""
    from .decision_engine import build_narrative_from_classifications

    return build_narrative_from_classifications(classifications)


def sanitize_provisional_narrative(narrative: str, classifications: list[dict[str, Any]]) -> str:
    """Remplace le narrative LLM par une reformulation des decisions structurees."""
    items = [item for item in classifications if isinstance(item, dict)]
    if items:
        from .decision_engine import build_narrative_from_classifications

        return build_narrative_from_classifications(items)

    text = (narrative or "").strip()
    if not text:
        return text

    body = _PROPOSITION_BOILERPLATE_RE.sub("", text).strip()
    body = re.sub(r"\s{2,}", " ", body).strip()
    body = _INCOMPLETE_NARRATIVE_TAIL_RE.sub("", body).strip()
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
    elif looks_like_structured_dossier(source_block):
        product = _extract_product_name_from_source(source_block)
        if product:
            item["product_name"] = product
            item["description"] = product
    else:
        description = str(item.get("description") or "")
        if description and (
            "surface exterieure" in _normalize(description)
            or "surface mixte" in _normalize(description)
        ):
            item["description"] = _strip_llm_exterior_hallucinations(description)

    justification = str(item.get("justification") or "")
    justification = _strip_false_rgi3_claims(justification)
    item["justification"] = justification


def apply_early_subposition_gate(item: dict[str, Any], source_text: str | None = None) -> None:
    """
    Première passe TEC avant les RGI : le code renvoyé par le LLM n'est qu'une hypothèse.
    Tronque au dernier niveau justifiable si la sous-position n'est pas confirmable.
    """
    source = (source_text or item.get("source_query") or item.get("description") or "").strip()
    hs = str(item.get("hs_code") or "").strip()
    if not hs or not source:
        return

    from .tariff_subposition import apply_subposition_resolution

    if _hs_digit_count(hs) > 4:
        item.setdefault("hs_code_suggested", hs)

    apply_subposition_resolution(item, source_text=source)

    resolution = item.get("subposition_resolution")
    if isinstance(resolution, dict) and resolution.get("status") != "confirmed":
        item["classification_status"] = "provisoire"
        cap = resolution.get("confidence_cap")
        if isinstance(cap, (int, float)):
            try:
                current = int(round(float(item.get("confidence") or 90)))
            except (TypeError, ValueError):
                current = 90
            item["confidence"] = min(current, int(cap))


def apply_completeness_adjustments(item: dict[str, Any], source_text: str | None = None) -> None:
    """Enrichit la classification et ajuste confiance/statut si informations critiques manquent."""
    source = (source_text or item.get("source_query") or item.get("description") or "").strip()
    backfill_commercial_fields_from_source(item, source)
    original_hs = _prepare_item_for_criteria_reevaluation(item, source)
    analysis = analyze_classification_completeness(source_text=source, item=item)
    item["completeness_checklist"] = analysis["checklist"]
    item["missing_fields"] = analysis["missing_fields"]
    item["completeness_score"] = analysis["completeness_score"]
    item["classification_status"] = analysis["classification_status"]
    item["requires_exterior_surface"] = analysis["requires_exterior_surface"]
    item["subposition_detail_required"] = analysis["subposition_detail_required"]

    from .tariff_subposition import apply_subposition_resolution

    subdivision = apply_subposition_resolution(item, source_text=source)
    subdivision_confirmed = subdivision.status == "confirmed"

    if subdivision.missing_criteria and not subdivision_confirmed:
        analysis["missing_critical"] = subdivision.missing_criteria
        analysis["can_classify_confidently"] = False
        analysis["classification_status"] = "provisoire"
        analysis["requires_exterior_surface"] = any(
            "surface exterieure" in _normalize(field) for field in subdivision.missing_criteria
        )
        item["missing_fields"] = subdivision.missing_criteria + analysis.get("missing_optional", [])
        item["classification_status"] = "provisoire"
        item["requires_exterior_surface"] = analysis["requires_exterior_surface"]
    elif subdivision_confirmed:
        analysis["missing_critical"] = []
        analysis["can_classify_confidently"] = True
        analysis["requires_exterior_surface"] = False
        item["missing_fields"] = analysis.get("missing_optional", [])
        item.pop("requires_exterior_surface", None)

    if subdivision_confirmed and not analysis["missing_critical"]:
        item["classification_status"] = "confirmee"

    if not analysis["can_classify_confidently"]:
        confidence = item.get("confidence")
        try:
            current_conf = int(round(float(confidence)))
        except (TypeError, ValueError):
            current_conf = 90
        item["confidence"] = min(current_conf, 65)

    hs_digits = re.sub(r"\D", "", str(item.get("hs_code") or ""))
    if not subdivision_confirmed:
        original_digits = re.sub(r"\D", "", original_hs)
        if len(original_digits) > 4:
            item["hs_code_suggested"] = original_hs
        if len(hs_digits) > 4:
            _apply_provisional_position_level(item, analysis)
        _sanitize_provisional_item_text(item, source_text=source, analysis=analysis)
    else:
        item.pop("hs_code_suggested", None)
        _sanitize_provisional_item_text(item, source_text=source, analysis=analysis)

    from .classification_coherence import enforce_classification_coherence
    from .decision_engine import render_outputs_from_decision

    enforce_classification_coherence(item)
    render_outputs_from_decision(item, source)

    if item.get("description_quality") is not None and analysis["requires_exterior_surface"]:
        try:
            item["description_quality"] = min(int(item["description_quality"]), 78)
        except (TypeError, ValueError):
            item["description_quality"] = 78
