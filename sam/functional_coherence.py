"""Generic functional compatibility gate for a selected TEC classification."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .functional_profile import build_functional_profile
from .tariff_labels import list_subpositions_for_position, lookup_position_label
from .tariff_metadata import get_position_heading
from .tariff_position_rules import position_code_from_hs
from .telemetry import increment_telemetry


_STOPWORDS = {
    "avec", "autre", "autres", "dans", "des", "dont", "elle", "elles",
    "pour", "sans", "sous", "une", "unit", "unite", "units", "produit",
    "appareil", "appareils", "machine", "machines", "partie", "parties",
    "ainsi", "compris", "denomme", "denommes", "ailleurs", "non",
}


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _terms(value: Any) -> set[str]:
    words = set(re.findall(r"[a-z0-9]{4,}", _normalize(value))) - _STOPWORDS
    terms = set(words)
    for word in words:
        if len(word) >= 7:
            terms.add(word[:6])
        elif len(word) >= 5:
            terms.add(word[:5])
    return terms


def _affinity(profile_text: str, label: str) -> float:
    profile_terms = _terms(profile_text)
    label_terms = _terms(label)
    if not profile_terms or not label_terms:
        return 0.0
    matches = profile_terms & label_terms
    return len(matches) / max(1, min(len(profile_terms), len(label_terms)))


def _profile_text(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None,
) -> str:
    identification = product_identification if isinstance(product_identification, dict) else {}
    profile = identification.get("functional_profile")
    if isinstance(profile, dict):
        values = [
            str(profile.get(key) or "")
            for key in [
                "product_type",
                "primary_function",
                "characteristics",
                "family",
                "system_role",
            ]
        ]
        semantic_terms = profile.get("semantic_terms")
        if isinstance(semantic_terms, list):
            values.extend(str(term) for term in semantic_terms)
        return " ".join(values).strip()
    source = str(item.get("source_query") or item.get("description") or "")
    return build_functional_profile(source, identification).functional_query()


def _selected_label(item: dict[str, Any], hs_code: str) -> str:
    subposition = str(item.get("subposition_label") or "").strip()
    if subposition and "a determiner" not in _normalize(subposition):
        return subposition
    position = str(item.get("position_label") or "").strip()
    return position or lookup_position_label(hs_code) or get_position_heading(hs_code) or ""


def _candidate_labels(candidates: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates or []:
        position = str(candidate.get("position_code") or "").strip()
        if not position:
            continue
        position_label = get_position_heading(position) or str(candidate.get("label") or "").strip()
        if position_label and (position, position_label) not in seen:
            labels.append((position, position_label))
            seen.add((position, position_label))
        for code, label in list_subpositions_for_position(position):
            entry = (str(code).strip(), str(label).strip())
            if entry[0] and entry[1] and entry not in seen:
                labels.append(entry)
                seen.add(entry)
    return labels


def _has_system_media_conflict(profile_text: str, selected_label: str, system_role: str) -> bool:
    if system_role != "standalone_system":
        return False
    profile_terms = _terms(profile_text)
    label_terms = _terms(selected_label)
    storage_system_terms = {"storage", "stockage", "system", "systeme", "unit", "unite", "baie"}
    media_carrier_terms = {
        "support", "supports", "media", "disque", "disques", "bande", "bandes",
        "carte", "cartes", "enregistrement", "recording",
    }
    return bool(profile_terms & storage_system_terms and label_terms & media_carrier_terms)


def _has_device_family_conflict(profile_text: str, hs_code: str) -> bool:
    """Reject broad lexical matches that contradict the product's functional family."""
    normalized = _normalize(profile_text)
    words = set(normalized.split())
    position = position_code_from_hs(hs_code)

    modern_camera_terms = {
        "digital", "numerique", "video", "television", "thermal", "thermique",
        "infrared", "infrarouge", "multispectral", "surveillance", "network", "reseau",
        "imaging", "imagerie",
    }
    cinematographic_terms = {"cinema", "cinematographic", "cinematographique", "film", "pellicule"}
    if (
        position == "90.07"
        and words & modern_camera_terms
        and not words & cinematographic_terms
    ):
        return True

    tablet_terms = {"tablet", "tablette"}
    if position == "85.17" and re.sub(r"\D", "", hs_code).startswith("851713"):
        return bool(words & tablet_terms)

    medical_device_terms = {
        "seringue", "seringues", "syringe", "aiguille", "aiguilles",
        "medical", "medicale", "medicales", "medicaux", "sterile", "injection",
    }
    radiology_terms = {
        "rayons", "radiations", "radiographie", "radiotherapie",
        "tomographie", "ionisantes", "x",
    }
    if position == "90.22" and words & medical_device_terms and not words & radiology_terms:
        return True

    return False


def check_functional_coherence(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    hs_code = str(item.get("hs_code") or "").strip()
    if not hs_code or not re.sub(r"\D", "", hs_code):
        return {
            "status": "unresolved",
            "reason": "Aucun code TEC exploitable n'a ete produit.",
            "selected_affinity": 0.0,
        }

    effective_identification = (
        dict(product_identification)
        if isinstance(product_identification, dict)
        else {}
    )
    if not isinstance(effective_identification.get("functional_profile"), dict):
        source = str(item.get("source_query") or item.get("description") or "")
        inferred_profile = build_functional_profile(source, effective_identification)
        effective_identification["functional_profile"] = inferred_profile.to_dict()

    profile_text = _profile_text(item, effective_identification)
    selected_label = _selected_label(item, hs_code)
    if not profile_text or not selected_label:
        return None
    selected_score = _affinity(profile_text, selected_label)
    profile_data = (
        effective_identification.get("functional_profile")
        if isinstance(effective_identification, dict)
        else None
    )
    system_role = str((profile_data or {}).get("system_role") or "") if isinstance(profile_data, dict) else ""
    structural_conflict = _has_system_media_conflict(
        profile_text,
        selected_label,
        system_role,
    ) or _has_device_family_conflict(profile_text, hs_code)

    candidates = item.get("tec_position_candidates")
    if not isinstance(candidates, list):
        candidates = []
    alternatives = _candidate_labels(candidates)
    best_code = ""
    best_label = ""
    best_score = 0.0
    selected_digits = re.sub(r"\D", "", hs_code)
    for code, label in alternatives:
        code_digits = re.sub(r"\D", "", code)
        if code_digits and selected_digits.startswith(code_digits):
            continue
        score = _affinity(profile_text, label)
        if score > best_score:
            best_code, best_label, best_score = code, label, score

    if structural_conflict or (
        selected_score <= 0.05
        and best_score >= 0.08
        and best_score >= selected_score + 0.05
    ):
        return {
            "status": "incompatible",
            "reason": (
                "Le libelle TEC selectionne ne correspond pas a la fonction ou au role "
                "systeme/composant decrit par les informations produit."
            ),
            "selected_label": selected_label,
            "selected_affinity": round(selected_score, 3),
            "suggested_candidate": best_code,
            "suggested_label": best_label,
            "suggested_affinity": round(best_score, 3),
        }
    if selected_score >= 0.12:
        return {
            "status": "compatible",
            "selected_label": selected_label,
            "selected_affinity": round(selected_score, 3),
        }
    return None


def apply_functional_coherence_gate(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None,
) -> bool:
    result = check_functional_coherence(item, product_identification)
    if not result:
        return False
    status = str(result.get("status") or "")
    item["functional_coherence"] = result
    if status == "compatible":
        return False

    item["classification_status"] = "provisoire"
    try:
        confidence = int(round(float(item.get("confidence") or 90)))
    except (TypeError, ValueError):
        confidence = 90
    cap = 40 if status == "unresolved" else 50
    item["confidence"] = min(confidence, cap)
    item["classification_confidence"] = min(
        int(round(float(item.get("classification_confidence") or confidence))),
        cap,
    )
    warning = str(result.get("reason") or "Coherence fonctionnelle non confirmee.")
    item["functional_coherence_warning"] = warning
    justification = str(item.get("justification") or "").strip()
    if warning not in justification:
        item["justification"] = f"[Controle fonctionnel] {warning} {justification}".strip()
    increment_telemetry(
        "functional_coherence_unresolved" if status == "unresolved" else "functional_contradictions"
    )
    return True


def enforce_functional_coherence_cap(item: dict[str, Any]) -> bool:
    """Preserve a previously detected contradiction after later normalization stages."""
    result = item.get("functional_coherence")
    if not isinstance(result, dict):
        return False
    status = str(result.get("status") or "").strip().lower()
    if status not in {"incompatible", "unresolved"}:
        return False

    cap = 40 if status == "unresolved" else 50
    item["classification_status"] = "provisoire"
    for field in ("confidence", "classification_confidence"):
        try:
            current = int(round(float(item.get(field) or 90)))
        except (TypeError, ValueError):
            current = 90
        item[field] = min(current, cap)
    return True
