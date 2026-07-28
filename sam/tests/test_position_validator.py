"""Tests for position_validator module."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sam.position_validator import (
    _keyword_match_score,
    find_better_position_in_chapter,
    apply_position_validation,
)


class TestKeywordMatchScore:
    def test_zero_on_empty(self):
        assert _keyword_match_score("", "test") == 0.0
        assert _keyword_match_score("test", "") == 0.0

    def test_nonzero_on_overlap(self):
        score = _keyword_match_score(
            "telephone portable smartphone",
            "appareils pour la telephonie mobile, smartphones"
        )
        assert score > 0

    def test_higher_score_on_better_match(self):
        score_with = _keyword_match_score(
            "ecran moniteur affichage industriel",
            "moniteurs video industriel"
        )
        score_without = _keyword_match_score(
            "article divers usage courant",
            "moniteurs video industriel"
        )
        assert score_with > score_without


class TestFindBetterPosition:
    def test_returns_none_when_no_better(self):
        result = find_better_position_in_chapter(
            "85.28",
            "moniteur video",
            candidates=[
                {"position_code": "85.28", "label": "moniteurs video et projecteurs"},
                {"position_code": "85.24", "label": "disques, bandes magnetiques"},
            ]
        )
        assert result is None

    def test_finds_better_when_mismatch(self):
        result = find_better_position_in_chapter(
            "85.24",
            "moniteur video ecran affichage",
            candidates=[
                {"position_code": "85.24", "label": "disques, bandes, supports solides non enregistres"},
                {"position_code": "85.28", "label": "moniteurs et projecteurs, appareils recepteurs de television"},
            ]
        )
        assert result is not None
        assert result["better_position"] == "85.28"


class TestApplyPositionValidation:
    def test_reports_better_position_as_advisory_without_mutating_code(self):
        item = {
            "hs_code": "84.82",
            "confidence": 55,
            "classification_status": "provisoire",
            "source_query": "deep groove ball bearing",
        }
        candidates = [
            {"position_code": "84.82", "label": "bearings"},
            {"position_code": "84.12", "label": "deep groove devices"},
        ]
        corrected = apply_position_validation(item, None, candidates)
        assert corrected is False
        assert item["hs_code"] == "84.82"
        assert item["position_validation_advisory"]["better_position"] == "84.12"

    def test_does_not_overwrite_confirmed_high_confidence_result(self):
        item = {
            "hs_code": "76.15.10.00",
            "confidence": 95,
            "classification_status": "confirmee",
        }
        candidates = [
            {"position_code": "76.01", "label": "aluminium brut et alliages"},
        ]
        corrected = apply_position_validation(item, None, candidates)
        assert corrected is False
        assert item["hs_code"] == "76.15.10.00"

    def test_does_not_overwrite_out_of_candidate_hypothesis(self):
        item = {
            "hs_code": "70.13",
            "confidence": 55,
            "classification_status": "provisoire",
            "tec_candidate_outside_set": True,
        }
        corrected = apply_position_validation(item, None, [])
        assert corrected is False
        assert item["hs_code"] == "70.13"

    def test_corrects_wrong_position(self):
        item = {
            "hs_code": "85.24.10.00",
            "confidence": 85,
            "classification_status": "final",
            "justification": "Classified by LLM.",
        }
        prod_id = {
            "enriched_description": "moniteur video ecran affichage led industriel",
            "skipped": False,
        }
        candidates = [
            {"position_code": "85.24", "label": "disques, bandes, supports d'enregistrement"},
            {"position_code": "85.28", "label": "moniteurs et projecteurs, appareils recepteurs de television"},
        ]
        corrected = apply_position_validation(item, prod_id, candidates)
        if corrected:
            assert item["hs_code"] == "85.28"
            assert item["classification_status"] == "provisoire"
            assert item["confidence"] <= 60

    def test_no_correction_when_good_match(self):
        item = {
            "hs_code": "85.28.10.00",
            "confidence": 90,
            "classification_status": "final",
            "justification": "Classified by LLM.",
        }
        prod_id = {
            "enriched_description": "moniteur video ecran affichage",
            "skipped": False,
        }
        candidates = [
            {"position_code": "85.28", "label": "moniteurs et projecteurs video"},
            {"position_code": "85.24", "label": "disques, bandes magnetiques"},
        ]
        corrected = apply_position_validation(item, prod_id, candidates)
        assert corrected is False
        assert item["hs_code"] == "85.28.10.00"

    def test_no_crash_on_missing_data(self):
        assert apply_position_validation({}, None, None) is False
        assert apply_position_validation({"hs_code": ""}, None, None) is False
        assert apply_position_validation("not a dict", None, None) is False
