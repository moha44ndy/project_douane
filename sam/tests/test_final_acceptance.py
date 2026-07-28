import tempfile
import unittest
from pathlib import Path

from sam.final_acceptance import evaluate_acceptance, load_last_telemetry


def _accepted_items() -> list[dict]:
    rows = [
        ("Cisco Catalyst 9300", "8517.62.00.00", "85.17"),
        ("Huawei OceanStor Dorado", "84.71", "84.71"),
        ("DJI Zenmuse H30T", "85.25", "85.25"),
        ("iPad Pro M4", "8471.41", "84.71"),
        ("KUKA KR 16 R1610", "8479.50.00.00", "84.79"),
        ("Omron NX102-1200", "8537.10.00.00", "85.37"),
        ("ABB ACS880-01-430A-3", "85.04", "85.04"),
    ]
    return [
        {
            "description": name,
            "source_query": name,
            "hs_code": code,
            "classification_status": "provisoire",
            "justification": "Classification provisoire avec justification technique.",
            "tec_position_candidates": [{"position_code": candidate}],
        }
        for name, code, candidate in rows
    ]


class TestFinalAcceptance(unittest.TestCase):
    def test_selective_gate_accepts_six_hits_and_one_call(self) -> None:
        report = evaluate_acceptance(
            _accepted_items(),
            {
                "counters": {
                    "structured_item_cache_hit": 6,
                    "classification_llm_calls": 1,
                }
            },
            1,
            mode="selective",
        )
        self.assertTrue(report["passed"], report["failed_checks"])

    def test_warm_gate_rejects_any_paid_call(self) -> None:
        report = evaluate_acceptance(
            _accepted_items(),
            {
                "counters": {
                    "structured_item_cache_hit": 7,
                    "classification_llm_calls": 1,
                }
            },
            0,
            mode="warm",
        )
        self.assertFalse(report["passed"])
        self.assertIn("warm_zero_llm_calls", report["failed_checks"])

    def test_retryable_placeholder_fails_quality_gate(self) -> None:
        items = _accepted_items()
        items[-1].update({"hs_code": "Non renseigne", "retryable": True})
        report = evaluate_acceptance(
            items,
            {"counters": {"structured_item_cache_hit": 6}},
            0,
            mode="selective",
        )
        self.assertFalse(report["passed"])
        self.assertIn("no_retryable_rows", report["failed_checks"])
        self.assertIn("no_placeholders", report["failed_checks"])

    def test_unexplained_provisional_row_fails_quality_gate(self) -> None:
        items = _accepted_items()
        items[0].update({"justification": ""})
        report = evaluate_acceptance(
            items,
            {"counters": {"structured_item_cache_hit": 6}},
            0,
            mode="selective",
        )
        self.assertFalse(report["passed"])
        self.assertIn("provisional_rows_explained", report["failed_checks"])

    def test_provisional_row_with_recovery_warning_is_accepted(self) -> None:
        items = _accepted_items()
        items[0].update({
            "justification": "",
            "missing_code_recovery_warning": "Recovered heading kept provisional.",
        })
        report = evaluate_acceptance(
            items,
            {"counters": {"structured_item_cache_hit": 6}},
            0,
            mode="selective",
        )
        self.assertTrue(report["passed"], report["failed_checks"])

    def test_loads_last_telemetry_and_counts_embeddings(self) -> None:
        content = "\n".join([
            "start vectorisation de la requete",
            'INFO telemetry operation=classify_stream summary={"counters":{"classification_llm_calls":1}}',
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.log"
            path.write_text(content, encoding="utf-8")
            telemetry, embeddings = load_last_telemetry(path)
        self.assertEqual(embeddings, 1)
        self.assertEqual(telemetry["counters"]["classification_llm_calls"], 1)


if __name__ == "__main__":
    unittest.main()
