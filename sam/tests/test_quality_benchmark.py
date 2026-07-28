import json
import tempfile
import unittest
from pathlib import Path

from sam.quality_benchmark import (
    ExpectedClassification,
    align_results,
    load_actual_classifications,
    load_expected_benchmark,
    normalize_hs_code,
    release_benchmark_errors,
    score_benchmark,
)


class TestQualityBenchmark(unittest.TestCase):
    def test_normalize_hs_code(self) -> None:
        self.assertEqual(normalize_hs_code("85.17.62.00.00"), "8517620000")
        self.assertEqual(normalize_hs_code("Non renseigne"), "")

    def test_loads_nested_raw_api_response(self) -> None:
        payload = {
            "raw": json.dumps(
                {
                    "narrative": "test",
                    "classifications": [{"hs_code": "8517.62", "description": "switch"}],
                }
            )
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            actual = load_actual_classifications(path)
        self.assertEqual(actual[0]["hs_code"], "8517.62")

    def test_alignment_uses_designation_when_results_are_reordered(self) -> None:
        expected = [
            ExpectedClassification("Solar module", "85", "8541", "854143"),
            ExpectedClassification("Coffee beans", "09", "0901", "090121"),
        ]
        actual = [
            {"source_query": "Produit : Coffee beans", "hs_code": "0901.21"},
            {"source_query": "Produit : Solar module", "hs_code": "8541.43"},
        ]
        aligned = align_results(expected, actual)
        self.assertEqual(aligned[0][1]["hs_code"], "8541.43")
        self.assertEqual(aligned[1][1]["hs_code"], "0901.21")
        self.assertEqual(aligned[0][2], "designation")

    def test_scores_hs6_heading_chapter_and_mismatch(self) -> None:
        expected = [
            ExpectedClassification("Exact", "85", "8541", "854143"),
            ExpectedClassification("Heading", "85", "8544", "854449"),
            ExpectedClassification("Chapter", "84", "8413", "841370"),
            ExpectedClassification("Wrong", "40", "4011", "401110"),
        ]
        actual = [
            {"source_query": "Exact", "hs_code": "8541.43.00.00"},
            {"source_query": "Heading", "hs_code": "8544.42.00.00"},
            {"source_query": "Chapter", "hs_code": "8415.10.00.00"},
            {"source_query": "Wrong", "hs_code": "8708.70.00.00"},
        ]
        rows, summary = score_benchmark(expected, actual)
        self.assertEqual([row["outcome"] for row in rows], [
            "exact_hs6",
            "heading_only",
            "chapter_only",
            "mismatch",
        ])
        self.assertEqual(summary["exact_hs6"], 1)
        self.assertEqual(summary["heading_or_better"], 2)
        self.assertEqual(summary["chapter_or_better"], 3)
        self.assertEqual(summary["exact_hs6_rate"], 0.25)

    def test_missing_result_is_reported(self) -> None:
        expected = [ExpectedClassification("Missing", "90", "9018", "901831")]
        rows, summary = score_benchmark(expected, [])
        self.assertEqual(rows[0]["outcome"], "missing_result")
        self.assertEqual(summary["missing_results"], 1)

    def test_loads_optional_split_and_input_type(self) -> None:
        csv_text = (
            "designation,expected_chapter2,expected_heading4,expected_hs6,label_status,"
            "dataset_split,input_type\n"
            "Industrial controller,85,8537,853710,customs_expert_reviewed,holdout,"
            "manufacturer_reference\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "benchmark.csv"
            path.write_text(csv_text, encoding="utf-8")
            expected = load_expected_benchmark(path)
        self.assertEqual(expected[0].dataset_split, "holdout")
        self.assertEqual(expected[0].input_type, "manufacturer_reference")
        self.assertTrue(expected[0].is_expert_reviewed)

    def test_scores_candidate_recall_and_false_high_confidence(self) -> None:
        expected = [ExpectedClassification("Switch", "85", "8517", "851762")]
        actual = [{
            "source_query": "Switch",
            "hs_code": "8517.13.00.00",
            "confidence": 95,
            "tec_position_candidates": [{"position_code": "85.17"}],
        }]
        rows, summary = score_benchmark(expected, actual)
        self.assertTrue(rows[0]["candidate_heading_recall"])
        self.assertFalse(rows[0]["false_high_confidence"])
        self.assertEqual(summary["candidate_heading_recall_rate"], 1.0)

        actual[0]["hs_code"] = "8471.30.00.00"
        rows, summary = score_benchmark(expected, actual)
        self.assertTrue(rows[0]["false_high_confidence"])
        self.assertEqual(summary["false_high_confidence_items"], 1)

    def test_release_gate_rejects_current_non_official_small_dataset(self) -> None:
        expected = [ExpectedClassification("Sample", "85", "8517", "851762")]
        errors = release_benchmark_errors(expected)
        self.assertIn("release benchmark must contain at least 100 items", errors)
        self.assertIn("all release labels must be customs-expert reviewed", errors)
        self.assertIn("release benchmark must contain an untouched holdout split", errors)
        self.assertIn(
            "release benchmark must contain at least 30 manufacturer-reference items",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
