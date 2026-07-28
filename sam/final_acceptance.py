"""Zero-cost scorer for the final Mosam seven-product acceptance run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .client_feedback_benchmark import (
    load_client_feedback_benchmark,
    score_client_feedback,
)
from .quality_benchmark import load_actual_classifications


_TELEMETRY_MARKER = "telemetry operation=classify_stream summary="


def load_last_telemetry(log_path: Path) -> tuple[dict[str, Any], int]:
    text = log_path.read_text(encoding="utf-8-sig", errors="replace")
    summaries: list[dict[str, Any]] = []
    for line in text.splitlines():
        if _TELEMETRY_MARKER not in line:
            continue
        raw = line.split(_TELEMETRY_MARKER, 1)[1].strip()
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            summaries.append(decoded)
    if not summaries:
        raise ValueError("No classify_stream telemetry summary found in log")
    embedding_calls = text.count("start vectorisation de la requete")
    return summaries[-1], embedding_calls


def _counter(telemetry: dict[str, Any], name: str) -> int:
    counters = telemetry.get("counters")
    if not isinstance(counters, dict):
        return 0
    try:
        return int(counters.get(name) or 0)
    except (TypeError, ValueError):
        return 0


def _has_provisional_explanation(item: dict[str, Any]) -> bool:
    if str(item.get("classification_status") or "").casefold() != "provisoire":
        return True
    text_fields = [
        item.get("justification"),
        item.get("functional_coherence_warning"),
        item.get("missing_code_recovery_warning"),
        item.get("candidate_evidence_warning"),
        item.get("subposition_label"),
        ((item.get("subposition_resolution") or {}) if isinstance(item.get("subposition_resolution"), dict) else {}).get("explanation"),
    ]
    return any(str(value or "").strip() for value in text_fields)


def evaluate_acceptance(
    classifications: list[dict[str, Any]],
    telemetry: dict[str, Any],
    embedding_calls: int,
    *,
    mode: str,
    expected_items: int = 7,
) -> dict[str, Any]:
    expected = load_client_feedback_benchmark()
    rows, benchmark = score_client_feedback(expected, classifications)
    retryable = sum(1 for item in classifications if item.get("retryable"))
    placeholders = sum(
        1
        for item in classifications
        if len(re.sub(r"\D", "", str(item.get("hs_code") or ""))) < 4
    )
    confirmed_placeholders = sum(
        1
        for item in classifications
        if str(item.get("classification_status") or "").casefold() == "confirmee"
        and len(re.sub(r"\D", "", str(item.get("hs_code") or ""))) < 4
    )
    unexplained_provisional = sum(
        1
        for item in classifications
        if isinstance(item, dict) and not _has_provisional_explanation(item)
    )

    llm_calls = _counter(telemetry, "classification_llm_calls")
    item_cache_hits = _counter(telemetry, "structured_item_cache_hit")
    full_cache_hits = _counter(telemetry, "classify_cache_hit")
    checks = {
        "result_count": len(classifications) == expected_items,
        "no_retryable_rows": retryable == 0,
        "no_placeholders": placeholders == 0,
        "no_confirmed_placeholders": confirmed_placeholders == 0,
        "provisional_rows_explained": unexplained_provisional == 0,
        "no_forbidden_headings": int(benchmark["forbidden_headings"]) == 0,
        "quality_outcomes": int(benchmark["accepted"]) >= 6,
        "candidate_recall": int(benchmark["candidate_recall_items"]) >= 6,
    }
    if mode == "selective":
        checks.update({
            "selective_cache_hits": item_cache_hits >= 6 or full_cache_hits >= 1,
            "selective_llm_budget": llm_calls <= 1,
            "selective_embedding_budget": embedding_calls <= 1,
        })
    elif mode == "warm":
        checks.update({
            "warm_cache_hits": item_cache_hits >= expected_items or full_cache_hits >= 1,
            "warm_zero_llm_calls": llm_calls == 0,
            "warm_zero_embeddings": embedding_calls == 0,
        })
    else:
        raise ValueError(f"Unsupported acceptance mode: {mode}")

    failed = [name for name, passed in checks.items() if not passed]
    return {
        "mode": mode,
        "passed": not failed,
        "failed_checks": failed,
        "checks": checks,
        "metrics": {
            "results": len(classifications),
            "retryable_rows": retryable,
            "placeholders": placeholders,
            "confirmed_placeholders": confirmed_placeholders,
            "unexplained_provisional_rows": unexplained_provisional,
            "accepted_quality_outcomes": benchmark["accepted"],
            "candidate_recall_items": benchmark["candidate_recall_items"],
            "forbidden_headings": benchmark["forbidden_headings"],
            "classification_llm_calls": llm_calls,
            "embedding_calls": embedding_calls,
            "item_cache_hits": item_cache_hits,
            "full_cache_hits": full_cache_hits,
        },
        "products": rows,
        "notice": benchmark["reference_notice"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score final Mosam acceptance artifacts")
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--mode", choices=("selective", "warm"), required=True)
    parser.add_argument("--expected-items", type=int, default=7)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    classifications = load_actual_classifications(args.results)
    telemetry, embedding_calls = load_last_telemetry(args.log)
    report = evaluate_acceptance(
        classifications,
        telemetry,
        embedding_calls,
        mode=args.mode,
        expected_items=max(1, args.expected_items),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
