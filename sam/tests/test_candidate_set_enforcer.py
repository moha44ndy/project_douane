"""Tests du verrouillage des positions TEC candidates."""

from __future__ import annotations

import unittest

from sam.candidate_set_enforcer import (
    build_position_candidates,
    enforce_candidate_set_on_item,
    extract_tariff_codes_from_text,
    format_candidate_set_prompt,
    enforce_candidate_evidence_cap,
    limit_position_candidates,
    recover_missing_heading_from_candidates,
    rerank_candidates_by_affinity,
    summarize_candidate_evidence,
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

    def test_limit_position_candidates_preserves_credible_chapter_diversity(self) -> None:
        candidates = [
            {"position_code": "85.17", "score": 10.0, "affinity_score": 0.1},
            {"position_code": "85.23", "score": 9.0, "affinity_score": 0.0},
            {"position_code": "85.28", "score": 8.0, "affinity_score": 0.0},
            {"position_code": "84.71", "score": 2.0, "affinity_score": 0.35},
            {"position_code": "90.06", "score": 1.8, "affinity_score": 0.3},
        ]

        limited = limit_position_candidates(candidates, max_positions=4)
        chapters = {entry["chapter"] for entry in limited}

        self.assertEqual(len(limited), 4)
        self.assertIn("84", chapters)
        self.assertIn("90", chapters)

    def test_candidate_summary_is_tariff_neutral(self) -> None:
        summary = summarize_candidate_evidence([
            {
                "position_code": "85.17",
                "affinity_score": 0.4,
                "candidate_sources": ["faiss", "functional_heading_match"],
            },
            {"position_code": "84.71", "affinity_score": 0.2, "candidate_sources": ["faiss"]},
        ])

        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["chapter_count"], 2)
        self.assertEqual(summary["max_affinity"], 0.4)
        self.assertEqual(summary["sources"], ["faiss", "functional_heading_match"])
        self.assertEqual(summary["chapter_ranking"][0]["chapter"], "85")

    def test_enforce_candidate_set_keeps_out_of_set_code_as_provisional(self) -> None:
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
        item["classification_confidence"] = 95
        corrected = enforce_candidate_set_on_item(item, candidates)
        self.assertFalse(corrected)
        self.assertEqual(item["hs_code"], "9007.11.00.00")
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(int(item["confidence"]), 55)
        self.assertLessEqual(int(item["classification_confidence"]), 55)
        self.assertTrue(item["candidate_evidence_weak"])
        self.assertTrue(item["tec_candidate_outside_set"])
        self.assertFalse(item["tec_candidate_locked"])

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

    def test_matching_but_weak_candidate_is_provisional_when_stronger_alternative_exists(self) -> None:
        item = {
            "hs_code": "8523.00.00.00",
            "confidence": 94,
            "classification_confidence": 94,
        }
        candidates = [
            {"position_code": "85.23", "affinity_score": 0.02},
            {"position_code": "84.71", "affinity_score": 0.42},
        ]

        enforce_candidate_set_on_item(item, candidates)

        self.assertTrue(item["candidate_evidence_weak"])
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(item["confidence"], 55)

        item["classification_status"] = "confirmee"
        item["confidence"] = 90
        self.assertTrue(enforce_candidate_evidence_cap(item))
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertEqual(item["confidence"], 55)

    def test_missing_code_recovers_unique_direct_heading_provisionally(self) -> None:
        item = {"hs_code": "", "confidence": 90, "classification_status": "confirmee"}
        candidates = [
            {
                "position_code": "84.71",
                "score": 10.75,
                "candidate_sources": ["direct_label_keywords"],
            },
            {
                "position_code": "85.17",
                "score": 2.0,
                "candidate_sources": ["faiss"],
            },
        ]

        self.assertTrue(recover_missing_heading_from_candidates(item, candidates))
        self.assertEqual(item["hs_code"], "84.71")
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(item["confidence"], 40)

    def test_missing_code_is_not_recovered_from_ambiguous_direct_headings(self) -> None:
        item = {"hs_code": "", "confidence": 90}
        candidates = [
            {
                "position_code": "84.71",
                "score": 10.5,
                "candidate_sources": ["direct_label_keywords"],
            },
            {
                "position_code": "85.28",
                "score": 10.5,
                "candidate_sources": ["direct_label_keywords"],
            },
        ]

        self.assertFalse(recover_missing_heading_from_candidates(item, candidates))
        self.assertEqual(item["hs_code"], "")

    def test_missing_code_recovers_strongest_compatible_heading(self) -> None:
        item = {"hs_code": "", "confidence": 90, "classification_status": "confirmee"}
        candidates = [
            {
                "position_code": "85.23",
                "score": 2.0,
                "compatibility_score": 0.0,
                "affinity_score": 0.01,
            },
            {
                "position_code": "84.71",
                "score": 1.6,
                "compatibility_score": 0.42,
                "affinity_score": 0.12,
            },
        ]

        self.assertTrue(recover_missing_heading_from_candidates(item, candidates))
        self.assertEqual(item["hs_code"], "84.71")
        self.assertEqual(item["classification_status"], "provisoire")

    def test_rerank_candidates_demotes_smartphone_family_for_tablet(self) -> None:
        candidates = [
            {"position_code": "85.17", "label": "Telephones intelligents", "score": 3.2},
            {"position_code": "84.71", "label": "Machines automatiques de traitement de l'information portatives", "score": 2.4},
        ]

        reranked = rerank_candidates_by_affinity(
            candidates,
            product_type="portable tablet or hybrid data processing computer",
            function_usage="execute applications and process data",
            family="tablet computer",
        )

        self.assertEqual(reranked[0]["position_code"], "84.71")
        self.assertGreater(reranked[0].get("compatibility_score", 0), 0)
        self.assertIn("compatibility_warning", reranked[1])

    def test_rerank_candidates_demotes_household_appliance_for_frequency_drive(self) -> None:
        candidates = [
            {"position_code": "85.08", "label": "Aspirateurs avec reservoir", "score": 4.0},
            {"position_code": "85.04", "label": "Convertisseurs statiques", "score": 2.0},
        ]

        reranked = rerank_candidates_by_affinity(
            candidates,
            product_type="static electrical power converter or variable speed drive",
            function_usage="regulate the speed of an electric motor",
            family="industrial frequency drive",
        )

        self.assertEqual(reranked[0]["position_code"], "85.04")
        self.assertIn("compatibility_warning", reranked[1])

    def test_rerank_candidates_demotes_radiology_for_medical_syringe(self) -> None:
        candidates = [
            {"position_code": "90.22", "label": "Appareils a rayons X et autres radiations ionisantes", "score": 4.0},
            {"position_code": "90.18", "label": "Instruments et appareils medico chirurgicaux", "score": 2.0},
        ]

        reranked = rerank_candidates_by_affinity(
            candidates,
            product_type="disposable medical syringe",
            function_usage="sterile injection for medical use",
            family="medical consumable",
        )

        self.assertEqual(reranked[0]["position_code"], "90.18")
        self.assertIn("compatibility_warning", reranked[1])

    def test_rerank_candidates_promotes_server_family_over_display_heading(self) -> None:
        candidates = [
            {"position_code": "85.28", "label": "Moniteurs et appareils d'affichage video", "score": 3.8},
            {"position_code": "84.71", "label": "Machines automatiques de traitement de l'information et leurs unites", "score": 2.6},
        ]

        reranked = rerank_candidates_by_affinity(
            candidates,
            product_type="server automatic data processing machine",
            function_usage="process enterprise data in a rack server",
            family="rack server",
        )

        self.assertEqual(reranked[0]["position_code"], "84.71")
        self.assertIn("compatibility_warning", reranked[1])

    def test_missing_code_recovers_mixed_reality_display_heading(self) -> None:
        item = {"hs_code": "", "confidence": 92, "classification_status": "confirmee"}
        candidates = [
            {
                "position_code": "85.28",
                "score": 2.2,
                "compatibility_score": 0.42,
                "affinity_score": 0.14,
            },
            {
                "position_code": "85.17",
                "score": 2.0,
                "compatibility_score": -0.22,
                "affinity_score": 0.02,
            },
        ]

        self.assertTrue(recover_missing_heading_from_candidates(item, candidates))
        self.assertEqual(item["hs_code"], "85.28")
        self.assertEqual(item["classification_status"], "provisoire")


if __name__ == "__main__":
    unittest.main()
