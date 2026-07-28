"""Repeatable quality scoring for Mosam classification benchmark results."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BENCHMARK = Path("sam/benchmarks/quality_benchmark_25_expected.csv")


@dataclass(frozen=True)
class ExpectedClassification:
    designation: str
    expected_chapter2: str
    expected_heading4: str
    expected_hs6: str
    reference_rationale: str = ""
    label_status: str = "benchmark_reference_non_official"
    dataset_split: str = "development"
    input_type: str = "description"

    @property
    def is_expert_reviewed(self) -> bool:
        return "expert_reviewed" in self.label_status.casefold()


def normalize_hs_code(value: Any) -> str:
    return "".join(re.findall(r"\d", str(value or "")))


def normalize_match_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_expected_benchmark(path: Path) -> list[ExpectedClassification]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected: list[ExpectedClassification] = []
    for row in rows:
        designation = str(row.get("designation") or "").strip()
        hs6 = normalize_hs_code(row.get("expected_hs6"))[:6]
        if not designation or len(hs6) != 6:
            raise ValueError(f"Invalid benchmark row: designation={designation!r}, hs6={hs6!r}")
        expected.append(
            ExpectedClassification(
                designation=designation,
                expected_chapter2=normalize_hs_code(row.get("expected_chapter2"))[:2],
                expected_heading4=normalize_hs_code(row.get("expected_heading4"))[:4],
                expected_hs6=hs6,
                reference_rationale=str(row.get("reference_rationale") or "").strip(),
                label_status=str(row.get("label_status") or "").strip()
                or "benchmark_reference_non_official",
                dataset_split=str(row.get("dataset_split") or "").strip()
                or "development",
                input_type=str(row.get("input_type") or "").strip()
                or "description",
            )
        )
    return expected


def _decode_json_layers(value: Any) -> Any:
    current = value
    for _ in range(4):
        if isinstance(current, str):
            current = json.loads(current)
            continue
        if isinstance(current, dict) and "raw" in current and not isinstance(
            current.get("classifications"), list
        ):
            current = current["raw"]
            continue
        break
    return current


def load_actual_classifications(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    with path.open("r", encoding="utf-8-sig") as handle:
        payload = _decode_json_layers(json.load(handle))
    if not isinstance(payload, dict) or not isinstance(payload.get("classifications"), list):
        raise ValueError("Results must contain a classifications array")
    return [dict(item) for item in payload["classifications"] if isinstance(item, dict)]


def _actual_match_text(item: dict[str, Any]) -> str:
    product_identification = item.get("product_identification")
    product_bits: list[str] = []
    if isinstance(product_identification, dict):
        product_bits = [
            str(product_identification.get("original_query") or ""),
            str(product_identification.get("product_name") or ""),
            str(product_identification.get("manufacturer_part_number") or ""),
        ]
    return normalize_match_text(
        " ".join(
            [
                str(item.get("source_query") or ""),
                str(item.get("description") or ""),
                *product_bits,
            ]
        )
    )


def _candidate_heading_recall(item: dict[str, Any], expected_heading4: str) -> bool:
    candidates = item.get("tec_position_candidates")
    if not isinstance(candidates, list):
        identification = item.get("product_identification")
        candidates = (
            identification.get("tec_position_candidates")
            if isinstance(identification, dict)
            else []
        )
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        digits = normalize_hs_code(candidate.get("position_code"))[:4]
        if digits and digits == expected_heading4:
            return True
    return False


def _normalized_confidence(item: dict[str, Any]) -> float | None:
    value = item.get("classification_confidence")
    if value is None:
        value = item.get("confidence")
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence > 1:
        confidence /= 100
    return min(max(confidence, 0.0), 1.0)


def align_results(
    expected: list[ExpectedClassification], actual: list[dict[str, Any]]
) -> list[tuple[ExpectedClassification, dict[str, Any] | None, str]]:
    unused = set(range(len(actual)))
    aligned: list[tuple[ExpectedClassification, dict[str, Any] | None, str]] = []
    actual_texts = [_actual_match_text(item) for item in actual]

    for expected_index, benchmark in enumerate(expected):
        needle = normalize_match_text(benchmark.designation)
        matched_index = next(
            (
                idx
                for idx in sorted(unused)
                if needle and needle in actual_texts[idx]
            ),
            None,
        )
        method = "designation"
        if matched_index is None and expected_index in unused:
            matched_index = expected_index
            method = "order_fallback"
        if matched_index is None:
            aligned.append((benchmark, None, "missing"))
            continue
        unused.remove(matched_index)
        aligned.append((benchmark, actual[matched_index], method))
    return aligned


def _score_row(
    expected: ExpectedClassification,
    actual: dict[str, Any] | None,
    alignment_method: str,
) -> dict[str, Any]:
    actual_code = normalize_hs_code((actual or {}).get("hs_code"))
    actual_hs6 = actual_code[:6] if len(actual_code) >= 6 else actual_code
    chapter_match = len(actual_code) >= 2 and actual_code[:2] == expected.expected_chapter2
    heading_match = len(actual_code) >= 4 and actual_code[:4] == expected.expected_heading4
    hs6_match = len(actual_code) >= 6 and actual_code[:6] == expected.expected_hs6

    if actual is None:
        outcome = "missing_result"
    elif not actual_code:
        outcome = "missing_code"
    elif hs6_match:
        outcome = "exact_hs6"
    elif heading_match:
        outcome = "heading_only"
    elif chapter_match:
        outcome = "chapter_only"
    else:
        outcome = "mismatch"

    confidence = _normalized_confidence(actual or {})
    candidate_recall = _candidate_heading_recall(actual or {}, expected.expected_heading4)
    false_high_confidence = bool(confidence is not None and confidence >= 0.8 and not heading_match)
    return {
        "designation": expected.designation,
        "expected_chapter2": expected.expected_chapter2,
        "expected_heading4": expected.expected_heading4,
        "expected_hs6": expected.expected_hs6,
        "actual_hs_code": str((actual or {}).get("hs_code") or ""),
        "actual_hs6": actual_hs6,
        "chapter_match": chapter_match,
        "heading_match": heading_match,
        "hs6_match": hs6_match,
        "outcome": outcome,
        "alignment_method": alignment_method,
        "confidence": confidence if confidence is not None else "",
        "candidate_heading_recall": candidate_recall,
        "false_high_confidence": false_high_confidence,
        "classification_status": str((actual or {}).get("classification_status") or ""),
        "risk_level": str((actual or {}).get("risk_level") or ""),
        "actual_description": str((actual or {}).get("description") or ""),
        "reference_rationale": expected.reference_rationale,
        "label_status": expected.label_status,
        "dataset_split": expected.dataset_split,
        "input_type": expected.input_type,
    }


def score_benchmark(
    expected: list[ExpectedClassification], actual: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [_score_row(*entry) for entry in align_results(expected, actual)]
    total = len(rows)
    exact = sum(1 for row in rows if row["hs6_match"])
    heading = sum(1 for row in rows if row["heading_match"])
    chapter = sum(1 for row in rows if row["chapter_match"])
    candidate_recall = sum(1 for row in rows if row["candidate_heading_recall"])
    expert_reviewed = sum(1 for item in expected if item.is_expert_reviewed)
    manufacturer_reference_items = sum(
        1 for item in expected if item.input_type.casefold() == "manufacturer_reference"
    )
    summary = {
        "benchmark_items": total,
        "actual_items": len(actual),
        "exact_hs6": exact,
        "heading_or_better": heading,
        "chapter_or_better": chapter,
        "missing_results": sum(1 for row in rows if row["outcome"] == "missing_result"),
        "missing_codes": sum(1 for row in rows if row["outcome"] == "missing_code"),
        "mismatches": sum(1 for row in rows if row["outcome"] == "mismatch"),
        "candidate_heading_recall_items": candidate_recall,
        "candidate_heading_recall_rate": round(candidate_recall / total, 4) if total else 0.0,
        "false_high_confidence_items": sum(
            1 for row in rows if row["false_high_confidence"]
        ),
        "expert_reviewed_items": expert_reviewed,
        "non_official_items": total - expert_reviewed,
        "manufacturer_reference_items": manufacturer_reference_items,
        "dataset_splits": sorted({item.dataset_split for item in expected}),
        "release_gate_eligible": bool(total and expert_reviewed == total),
        "exact_hs6_rate": round(exact / total, 4) if total else 0.0,
        "heading_or_better_rate": round(heading / total, 4) if total else 0.0,
        "chapter_or_better_rate": round(chapter / total, 4) if total else 0.0,
        "reference_notice": "Benchmark references are non-official and require customs expert validation.",
    }
    return rows, summary


def release_benchmark_errors(expected: list[ExpectedClassification]) -> list[str]:
    """Return reasons why a dataset cannot be used as a release-quality gate."""
    errors: list[str] = []
    if len(expected) < 100:
        errors.append("release benchmark must contain at least 100 items")
    if any(not item.is_expert_reviewed for item in expected):
        errors.append("all release labels must be customs-expert reviewed")
    holdout_items = [item for item in expected if item.dataset_split.casefold() == "holdout"]
    if not holdout_items:
        errors.append("release benchmark must contain an untouched holdout split")
    reference_items = [
        item
        for item in expected
        if item.input_type.casefold() == "manufacturer_reference"
    ]
    if len(reference_items) < 30:
        errors.append("release benchmark must contain at least 30 manufacturer-reference items")
    return errors


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty benchmark report")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Mosam classification quality")
    parser.add_argument("--results", required=True, type=Path, help="Frontend JSON or result CSV")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--report", type=Path, default=Path("quality_benchmark_report.csv"))
    parser.add_argument(
        "--require-release-dataset",
        action="store_true",
        help="Reject non-expert, undersized or non-holdout benchmark datasets",
    )
    args = parser.parse_args()

    expected = load_expected_benchmark(args.benchmark)
    if args.require_release_dataset:
        errors = release_benchmark_errors(expected)
        if errors:
            print(json.dumps({"release_dataset_errors": errors}, ensure_ascii=False, indent=2))
            return 2
    actual = load_actual_classifications(args.results)
    rows, summary = score_benchmark(expected, actual)
    write_report(args.report, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
