"""Journal technique RGI : source unique pour l'affichage (le LLM ne choisit pas les regles)."""

from __future__ import annotations

import re
from typing import Any, Literal

RgiJournalStatus = Literal["applied", "not_applicable", "not_evaluated"]

CANONICAL_RGI_RULES: tuple[str, ...] = (
    "RGI 1",
    "RGI 2 a",
    "RGI 2 b",
    "RGI 3",
    "RGI 3 a",
    "RGI 3 b",
    "RGI 3 c",
    "RGI 4",
    "RGI 5",
    "RGI 6",
)

_RGI3_CHILDREN = ("RGI 3 a", "RGI 3 b", "RGI 3 c")


def _hs_digit_count(hs_code: str | None) -> int:
    return len(re.sub(r"\D", "", str(hs_code or "")))


def _pipeline_records(pipeline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in pipeline.get("applied_rules") or []:
        if isinstance(record, dict) and record.get("rule"):
            indexed[str(record["rule"])] = {**record, "applied": True}
    for record in pipeline.get("not_applied_rules") or []:
        if isinstance(record, dict) and record.get("rule"):
            rule = str(record["rule"])
            if rule not in indexed:
                indexed[rule] = {**record, "applied": False}
    return indexed


def _entry(
    rule: str,
    status: RgiJournalStatus,
    reason: str = "",
    *,
    source: str = "rgi_pipeline",
) -> dict[str, str]:
    return {
        "rule": rule,
        "status": status,
        "reason": (reason or "").strip(),
        "source": source,
    }


def _resolve_rgi3_parent(
    records: dict[str, dict[str, Any]],
    child_entries: list[dict[str, str]],
) -> dict[str, str]:
    applied_child = next((e for e in child_entries if e["status"] == "applied"), None)
    if applied_child:
        return _entry("RGI 3", "applied", applied_child["reason"], source="derived")

    parent = records.get("RGI 3")
    if parent:
        status: RgiJournalStatus = "applied" if parent.get("applied") else "not_applicable"
        return _entry("RGI 3", status, str(parent.get("reason") or ""))

    if all(e["status"] == "not_evaluated" for e in child_entries):
        return _entry("RGI 3", "not_evaluated", "Non evaluee dans ce cas.")

    if any(e["status"] == "not_applicable" for e in child_entries):
        return _entry(
            "RGI 3",
            "not_applicable",
            "Aucune sous-regle 3 a/3 b/3 c declenchee.",
        )

    return _entry("RGI 3", "not_applicable", "Une seule position candidate apres RGI 1.")


def _refresh_rgi6_from_item(item: dict[str, Any]) -> dict[str, str]:
    resolution = item.get("subposition_resolution")
    resolution = resolution if isinstance(resolution, dict) else {}
    hs = str(item.get("hs_code") or "")
    digits = _hs_digit_count(hs)

    if item.get("subposition_status") == "a_determiner":
        stop = hs or str(resolution.get("hs_code") or "")
        stop_digits = _hs_digit_count(stop)
        if stop_digits > 4:
            from ..tariff_position_rules import position_code_from_hs

            stop = position_code_from_hs(stop) or stop
        return _entry(
            "RGI 6",
            "applied",
            f"Arret au niveau {stop} : sous-position non determinable avec les informations disponibles.",
            source="subposition_resolution",
        )

    if resolution.get("status") == "confirmed" and digits >= 8:
        return _entry(
            "RGI 6",
            "applied",
            f"Sous-position {hs} confirmee dans la position retenue.",
            source="subposition_resolution",
        )

    if digits >= 8:
        return _entry(
            "RGI 6",
            "applied",
            "Sous-position proposee dans la position retenue.",
            source="subposition_resolution",
        )

    return _entry(
        "RGI 6",
        "not_applicable",
        "Classement arrete au niveau position : RGI 6 non necessaire.",
        source="subposition_resolution",
    )


def build_rgi_technical_journal(
    item: dict[str, Any],
    *,
    pipeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Construit le journal RGI canonique a partir du pipeline moteur et de l'etat final de l'item.
    Le LLM ne doit pas alimenter ce journal.
    """
    pipeline_data = pipeline if isinstance(pipeline, dict) else {}
    if not pipeline_data:
        raw = item.get("rgi_pipeline")
        pipeline_data = raw if isinstance(raw, dict) else {}

    records = _pipeline_records(pipeline_data)
    entries: list[dict[str, str]] = []
    child_entries: list[dict[str, str]] = []

    for rule in CANONICAL_RGI_RULES:
        if rule == "RGI 3":
            continue
        if rule in _RGI3_CHILDREN:
            record = records.get(rule)
            if record:
                status: RgiJournalStatus = "applied" if record.get("applied") else "not_applicable"
                child = _entry(rule, status, str(record.get("reason") or ""))
            else:
                child = _entry(rule, "not_evaluated", "Non evaluee : etape non atteinte.")
            child_entries.append(child)
            entries.append(child)
            continue

        if rule == "RGI 6":
            entries.append(_refresh_rgi6_from_item(item))
            continue

        record = records.get(rule)
        if record:
            status = "applied" if record.get("applied") else "not_applicable"
            entries.append(_entry(rule, status, str(record.get("reason") or "")))
        else:
            entries.append(_entry(rule, "not_evaluated", "Non evaluee : etape non atteinte."))

    parent_rgi3 = _resolve_rgi3_parent(records, child_entries)
    insert_at = next(i for i, e in enumerate(entries) if e["rule"] == "RGI 3 a")
    entries.insert(insert_at, parent_rgi3)

    notes_record = records.get("Notes legales")
    if notes_record:
        entries.insert(
            0,
            _entry(
                "Notes legales",
                "applied" if notes_record.get("applied") else "not_applicable",
                str(notes_record.get("reason") or ""),
            ),
        )

    applied_rules = [e["rule"] for e in entries if e["status"] == "applied"]
    return {
        "entries": entries,
        "applied_rules": applied_rules,
        "stopped_at": str(pipeline_data.get("stopped_at") or ""),
        "source": "rgi_engine",
    }


def format_rgi_journal_text(journal: dict[str, Any]) -> str:
    """Texte lisible du journal (prefixes + / -, sans emoji)."""
    entries = journal.get("entries") if isinstance(journal.get("entries"), list) else []
    if not entries:
        return ""

    lines = ["RGI appliquees", ""]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rule = str(entry.get("rule") or "").strip()
        if not rule:
            continue
        status = str(entry.get("status") or "not_evaluated")
        reason = str(entry.get("reason") or "").strip()
        mark = "+" if status == "applied" else "-"
        if reason:
            lines.append(f"{mark} {rule} ({reason})")
        elif status == "not_evaluated":
            lines.append(f"{mark} {rule} (non evaluee)")
        else:
            lines.append(f"{mark} {rule}")
    return "\n".join(lines).strip()


def attach_rgi_journal_to_item(item: dict[str, Any]) -> dict[str, Any]:
    """Attache journal structure et texte reformulable sur l'item."""
    journal = build_rgi_technical_journal(item)
    item["rgi_journal"] = journal
    item["rgi_journal_text"] = format_rgi_journal_text(journal)

    applied_records = [
        {"rule": e["rule"], "reason": e["reason"]}
        for e in journal.get("entries", [])
        if isinstance(e, dict) and e.get("status") == "applied" and e.get("reason")
    ]
    not_applicable_records = [
        {"rule": e["rule"], "reason": e["reason"]}
        for e in journal.get("entries", [])
        if isinstance(e, dict) and e.get("status") == "not_applicable" and e.get("reason")
    ]
    item["rgi_applied_records"] = applied_records
    item["rgi_not_applicable_records"] = not_applicable_records
    item["rgi_applied"] = journal.get("applied_rules") or []
    return journal
