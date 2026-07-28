"""Quality scorer for the non-official client-feedback regression set."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .quality_benchmark import load_actual_classifications


DEFAULT_BENCHMARK = Path("sam/benchmarks/quality_benchmark_client_feedback_7.csv")


def _digits(value: Any) -> str:
    return "".join(re.findall(r"\d", str(value or "")))


def _name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _code_list(value: Any) -> tuple[str, ...]:
    return tuple(code for part in str(value or "").split(";") if (code := _digits(part)))


@dataclass(frozen=True)
class ClientFeedbackExpectation:
    designation: str
    expected_functional_family: str
    allowed_chapters: tuple[str, ...]
    allowed_headings: tuple[str, ...]
    forbidden_headings: tuple[str, ...]
    acceptance_note: str
    label_status: str


def load_client_feedback_benchmark(path: Path = DEFAULT_BENCHMARK) -> list[ClientFeedbackExpectation]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        ClientFeedbackExpectation(
            designation=str(row.get("designation") or "").strip(),
            expected_functional_family=str(row.get("expected_functional_family") or "").strip(),
            allowed_chapters=_code_list(row.get("allowed_chapters")),
            allowed_headings=_code_list(row.get("allowed_headings")),
            forbidden_headings=_code_list(row.get("forbidden_headings")),
            acceptance_note=str(row.get("acceptance_note") or "").strip(),
            label_status=str(row.get("label_status") or "").strip(),
        )
        for row in rows
        if str(row.get("designation") or "").strip()
    ]


def _result_text(item: dict[str, Any]) -> str:
    return _name(
        " ".join(
            [
                str(item.get("description") or ""),
                str(item.get("source_query") or ""),
            ]
        )
    )


def _candidate_positions(item: dict[str, Any]) -> tuple[str, ...]:
    candidates = item.get("tec_position_candidates")
    if not isinstance(candidates, list):
        identification = item.get("product_identification")
        candidates = identification.get("tec_position_candidates") if isinstance(identification, dict) else []
    positions: list[str] = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        digits = _digits(candidate.get("position_code"))
        if digits and digits not in positions:
            positions.append(digits)
    return tuple(positions)


def score_client_feedback(
    expected: list[ClientFeedbackExpectation],
    actual: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unused = set(range(len(actual)))
    rows: list[dict[str, Any]] = []
    actual_names = [_result_text(item) for item in actual]

    for expectation in expected:
        needle = _name(expectation.designation)
        match_index = next(
            (idx for idx in sorted(unused) if needle and needle in actual_names[idx]),
            None,
        )
        item = actual[match_index] if match_index is not None else None
        if match_index is not None:
            unused.remove(match_index)
        actual_code = _digits((item or {}).get("hs_code"))
        forbidden = bool(
            actual_code
            and any(actual_code.startswith(prefix) for prefix in expectation.forbidden_headings)
        )
        heading_allowed = bool(
            actual_code
            and any(actual_code.startswith(prefix) for prefix in expectation.allowed_headings)
        )
        chapter_allowed = bool(
            actual_code
            and any(actual_code.startswith(prefix) for prefix in expectation.allowed_chapters)
        )
        candidate_positions = _candidate_positions(item or {})
        candidate_recall = bool(
            candidate_positions
            and any(
                expected_heading.startswith(candidate_position)
                or candidate_position.startswith(expected_heading)
                for candidate_position in candidate_positions
                for expected_heading in expectation.allowed_headings
            )
        )

        if item is None:
            outcome = "missing_result"
        elif not actual_code:
            outcome = "missing_code"
        elif forbidden:
            outcome = "forbidden_heading"
        elif heading_allowed:
            outcome = "accepted_heading"
        elif chapter_allowed:
            outcome = "accepted_chapter_only"
        else:
            outcome = "mismatch"

        rows.append(
            {
                "designation": expectation.designation,
                "expected_functional_family": expectation.expected_functional_family,
                "actual_hs_code": str((item or {}).get("hs_code") or ""),
                "outcome": outcome,
                "forbidden_heading": forbidden,
                "confidence": (item or {}).get("confidence", ""),
                "classification_status": str((item or {}).get("classification_status") or ""),
                "candidate_positions": ";".join(candidate_positions),
                "candidate_recall": candidate_recall,
                "acceptance_note": expectation.acceptance_note,
                "label_status": expectation.label_status,
            }
        )

    accepted = sum(
        1 for row in rows if row["outcome"] in {"accepted_heading", "accepted_chapter_only"}
    )
    summary = {
        "benchmark_items": len(rows),
        "accepted": accepted,
        "accepted_rate": round(accepted / len(rows), 4) if rows else 0.0,
        "forbidden_headings": sum(1 for row in rows if row["forbidden_heading"]),
        "missing_codes": sum(1 for row in rows if row["outcome"] == "missing_code"),
        "mismatches": sum(1 for row in rows if row["outcome"] == "mismatch"),
        "candidate_recall_items": sum(1 for row in rows if row["candidate_recall"]),
        "candidate_recall_rate": round(
            sum(1 for row in rows if row["candidate_recall"]) / len(rows), 4
        ) if rows else 0.0,
        "reference_notice": "Client feedback labels are non-official and require customs-expert validation.",
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Score client-feedback regressions")
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--report", type=Path, default=Path("client_feedback_report.csv"))
    args = parser.parse_args()

    expected = load_client_feedback_benchmark(args.benchmark)
    actual = load_actual_classifications(args.results)
    rows, summary = score_client_feedback(expected, actual)
    with args.report.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
