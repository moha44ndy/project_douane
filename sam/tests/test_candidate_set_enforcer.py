"""Tests du verrouillage des positions TEC candidates."""

from __future__ import annotations

import unittest

from sam.candidate_set_enforcer import (
    build_position_candidates,
    enforce_candidate_set_on_item,
    extract_tariff_codes_from_text,
    format_candidate_set_prompt,
    limit_position_candidates,
)


class _Chunk:
    def __init__(self, content: str) -> None:
        self.page_content = content


class TestCandidateSetEnforcer(unittest.TestCase):
    def test_extract_tariff_codes_from_text(self) -> None:
        text = "8528.52.00.00 -- Moniteurs -- 8524.70.00.00 -- Circuits"
        codes = extract_tariff_codes_from_text(text)
        self.assertIn("8528.52.00.00", codes)
        self.assertIn("8524.70.00.00", codes)

    def test_build_position_candidates_limits_to_three(self) -> None:
        chunks = [
            _Chunk("8528.52.00.00 -- Moniteurs et projecteurs kg 20 1"),
            _Chunk("8524.70.00.00 -- Circuits integres kg 20 1"),
            _Chunk("8471.30.00.00 -- Machines automatiques kg 20 1"),
            _Chunk("9007.11.00.00 -- Cameras cinematographiques kg 20 1"),
        ]
        candidates = build_position_candidates(
            chunks,
            [0, 1, 2, 3],
            [0.1, 0.2, 0.3, 0.4],
            max_positions=3,
        )
        self.assertLessEqual(len(candidates), 3)
        ordered = [item.position_code for item in candidates]
        self.assertEqual(ordered[0], "85.28")
        self.assertNotIn("90.07", ordered)

    def test_format_candidate_set_prompt_requires_lock(self) -> None:
        from sam.candidate_set_enforcer import PositionCandidate

        prompt = format_candidate_set_prompt(
            [
                PositionCandidate(
                    position_code="85.28",
                    label="Moniteurs",
                    score=1.0,
                    matched_codes=["8528.52.00.00"],
                )
            ]
        )
        self.assertIn("VERROUILLAGE OBLIGATOIRE", prompt)
        self.assertIn("85.28", prompt)
        self.assertIn("ELIMINATION", prompt)
        self.assertIn("compatible", prompt)

    def test_limit_position_candidates_keeps_highest_scores(self) -> None:
        candidates = [
            {"position_code": "85.17", "label": "A", "score": 0.2},
            {"position_code": "85.36", "label": "B", "score": 1.5},
            {"position_code": "85.44", "label": "C", "score": 0.9},
            {"position_code": "85.38", "label": "D", "score": 0.1},
        ]
        limited = limit_position_candidates(candidates, max_positions=2)
        self.assertEqual(len(limited), 2)
        self.assertEqual(limited[0]["position_code"], "85.36")
        self.assertEqual(limited[1]["position_code"], "85.44")

    def test_enforce_candidate_set_rejects_out_of_set_code(self) -> None:
        item = {
            "hs_code": "9007.11.00.00",
            "confidence": 88,
            "justification": "RGI 1",
        }
        candidates = [
            {
                "position_code": "85.28",
                "label": "Moniteurs",
                "score": 1.0,
                "matched_codes": ["8528.52.00.00"],
            },
            {
                "position_code": "85.24",
                "label": "Circuits",
                "score": 0.8,
                "matched_codes": ["8524.70.00.00"],
            },
        ]
        corrected = enforce_candidate_set_on_item(item, candidates)
        self.assertTrue(corrected)
        self.assertEqual(item["hs_code"], "85.28")
        self.assertEqual(item["hs_code_suggested"], "9007.11.00.00")
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(int(item["confidence"]), 55)

    def test_enforce_candidate_set_accepts_matching_position(self) -> None:
        item = {"hs_code": "8528.52.00.00", "confidence": 82}
        candidates = [
            {
                "position_code": "85.28",
                "label": "Moniteurs",
                "score": 1.0,
                "matched_codes": ["8528.52.00.00"],
            }
        ]
        corrected = enforce_candidate_set_on_item(item, candidates)
        self.assertFalse(corrected)
        self.assertEqual(item["hs_code"], "8528.52.00.00")


if __name__ == "__main__":
    unittest.main()
