from __future__ import annotations

import unittest
from pathlib import Path

from sam.client_feedback_benchmark import (
    load_client_feedback_benchmark,
    score_client_feedback,
)


class TestClientFeedbackBenchmark(unittest.TestCase):
    def test_loads_seven_non_official_expectations(self) -> None:
        expected = load_client_feedback_benchmark(
            Path("sam/benchmarks/quality_benchmark_client_feedback_7.csv")
        )

        self.assertEqual(len(expected), 7)
        self.assertTrue(all("non_official" in item.label_status for item in expected))

    def test_detects_client_reported_forbidden_headings(self) -> None:
        expected = load_client_feedback_benchmark(
            Path("sam/benchmarks/quality_benchmark_client_feedback_7.csv")
        )
        actual = [
            {
                "description": item.designation,
                "hs_code": {
                    "Cisco Catalyst 9300": "8517.13.00.00",
                    "Huawei OceanStor Dorado": "8523",
                    "DJI Zenmuse H30T": "8517.13.00.00",
                    "iPad Pro M4": "8517.13.00.00",
                    "KUKA KR 16 R1610": "8714",
                    "Omron NX102-1200": "8471.49",
                    "ABB ACS880-01-430A-3": "",
                }[item.designation],
                "confidence": 95,
                "classification_status": "confirmee",
            }
            for item in expected
        ]

        rows, summary = score_client_feedback(expected, actual)

        self.assertEqual(summary["forbidden_headings"], 6)
        self.assertEqual(summary["missing_codes"], 1)
        self.assertEqual(summary["accepted"], 0)
        self.assertTrue(all(row["outcome"] != "accepted_heading" for row in rows))

    def test_accepts_heading_or_safe_chapter_outcomes(self) -> None:
        expected = load_client_feedback_benchmark(
            Path("sam/benchmarks/quality_benchmark_client_feedback_7.csv")
        )
        codes = ["8517.62", "8471", "8525", "8471.30", "8479.50", "8537.10", "8504.40"]
        actual = [
            {"description": item.designation, "hs_code": code}
            for item, code in zip(expected, codes)
        ]

        _rows, summary = score_client_feedback(expected, actual)

        self.assertEqual(summary["accepted"], 7)
        self.assertEqual(summary["forbidden_headings"], 0)

    def test_measures_candidate_position_recall_separately_from_final_answer(self) -> None:
        expected = load_client_feedback_benchmark(
            Path("sam/benchmarks/quality_benchmark_client_feedback_7.csv")
        )
        actual = [
            {
                "description": item.designation,
                "hs_code": "9999",
                "tec_position_candidates": [
                    {"position_code": f"{item.allowed_headings[0][:2]}.{item.allowed_headings[0][2:4]}"}
                ],
            }
            for item in expected
        ]

        rows, summary = score_client_feedback(expected, actual)

        self.assertEqual(summary["accepted"], 0)
        self.assertEqual(summary["candidate_recall_items"], 7)
        self.assertEqual(summary["candidate_recall_rate"], 1.0)
        self.assertTrue(all(row["candidate_recall"] for row in rows))


if __name__ == "__main__":
    unittest.main()
