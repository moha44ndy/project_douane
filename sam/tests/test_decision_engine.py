import unittest

from sam.classification_completeness import apply_completeness_adjustments, sanitize_provisional_narrative
from sam.decision_engine import (
    build_justification_from_decision,
    build_narrative_from_classifications,
    render_outputs_from_decision,
    synthesize_decision_from_final_item,
    ClassificationDecision,
    CriterionDecision,
)
from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index


class _Chunk:
    def __init__(self, content: str) -> None:
        self.page_content = content


class TestDecisionEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        chunks = [
            _Chunk(
                "4202.91.10.00 -- Presentes demonte importes pour l'industrie du montage kg 20 1\n"
                "4202.91.90.00 -- Autres kg 20 1"
            ),
        ]
        set_tariff_label_index(build_tariff_label_index(chunks))

    def test_justification_generated_from_decision_not_llm(self) -> None:
        decision = ClassificationDecision(
            product_identified="Sac de voyage",
            position_code="42.02",
            hs_code="4202.91",
            chapter="42",
            classification_status="provisoire",
            subposition_status="a_determiner",
            confidence=75,
            criteria=[
                CriterionDecision(
                    criterion_id="4202.91.10.00",
                    label="Presentes demonte importes pour l'industrie du montage",
                    status="missing",
                    tec_reference="4202.91.10.00",
                    detail="Etat de presentation : monte ou demonte/non monte (libelle TEC 4202.91.10.00)",
                )
            ],
            missing_criteria=[
                "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage"
            ],
            llm_hypothesis_hs="4202.91.90.00",
            rgi_applied_records=[{"rule": "RGI 1", "reason": "Position retenue selon le libelle TEC."}],
            subposition_resolution={
                "status": "insufficient",
                "explanation": "Sous-position non determinable : criteres discriminants du TEC non verifiables.",
                "missing_criteria": [
                    "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage"
                ],
            },
        )
        text = build_justification_from_decision(decision)
        self.assertIn("[TEC]", text)
        self.assertIn("4202.91", text)
        self.assertIn("non determinable", text.lower())
        self.assertNotIn("RGI 3 b", text)
        self.assertNotIn("criteres discriminants satisfaits", text.lower())
        self.assertIn("[Hypothese modele]", text)

    def test_resolved_subposition_is_not_described_as_undetermined_when_overall_provisional(self) -> None:
        decision = ClassificationDecision(
            product_identified="Industrial controller",
            position_code="42.02",
            hs_code="4202.91.90.00",
            chapter="42",
            classification_status="provisoire",
            subposition_status=None,
            confidence=55,
            subposition_resolution={
                "status": "confirmed",
                "matched_code": "4202.91.90.00",
                "explanation": "Une seule sous-position confirmee.",
            },
        )

        text = build_justification_from_decision(decision)

        self.assertIn("Sous-position 4202.91.90.00", text)
        self.assertNotIn("non determinable", text.lower())
        self.assertNotIn("Arret au niveau", text)

    def test_render_outputs_replaces_llm_justification(self) -> None:
        source = "Sac de voyage compose de 40% polyester et 35% cuir"
        item = {
            "hs_code": "42.02",
            "hs_code_suggested": "4202.91.90.00",
            "chapter": "42",
            "classification_status": "provisoire",
            "subposition_status": "a_determiner",
            "confidence": 65,
            "justification": "RGI 3 b : le cuir predomine. Code 4202.91.90.00 retenu.",
            "missing_fields": [
                "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage "
                "(critere discriminant TEC)"
            ],
            "subposition_resolution": {
                "status": "insufficient",
                "missing_criteria": [
                    "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage "
                    "(critere discriminant TEC)"
                ],
            },
            "rgi_pipeline": {
                "applied_rules": [{"rule": "RGI 1", "applied": True, "reason": "Position retenue."}],
                "not_applied_rules": [],
            },
        }
        render_outputs_from_decision(item, source)
        self.assertIn("classification_decision", item)
        self.assertNotIn("RGI 3 b :", item["justification"])
        self.assertNotIn("+ RGI 3 b", item["justification"])
        self.assertNotIn("4202.91.90", item["justification"])
        self.assertIn("[TEC]", item["justification"])
        self.assertIn("+ RGI 1", item["justification"])
        self.assertIn("rgi_journal", item)
        self.assertIn("criteria_decisions", item["classification_analysis"])
        self.assertEqual(item["classification_analysis"]["product_identified"], "Sac de voyage compose de 40% polyester et 35% cuir")

    def test_synthesize_reads_final_item_state(self) -> None:
        item = {
            "hs_code": "4202.91.90.00",
            "chapter": "42",
            "classification_status": "confirmee",
            "confidence": 90,
            "subposition_resolution": {"status": "confirmed", "matched_code": "4202.91.90.00"},
        }
        source = "Sac de voyage 100% cuir livre monte et neuf"
        decision = synthesize_decision_from_final_item(source_text=source, item=item)
        self.assertEqual(decision.hs_code, "4202.91.90.00")
        self.assertEqual(decision.classification_status, "confirmee")

    def test_narrative_replaces_llm_hallucination_for_leather_bag(self) -> None:
        source = (
            "sac de voyage haut de gamme destine au transport d'effets personnels "
            "composer de 100% de cuir provenant d'italie et acheter a 450000 dollars"
        )
        item = {
            "hs_code": "4202.91.90.00",
            "chapter": "42",
            "description": source,
            "confidence": 90,
        }
        apply_completeness_adjustments(item, source_text=source)
        llm_narrative = (
            "Proposition indicative, a faire valider avant toute utilisation officielle. "
            "29.90.00 'Autres'. La classification repose sur un sac en cuir demonte ou non monte."
        )
        narrative = sanitize_provisional_narrative(llm_narrative, [item])
        self.assertNotIn("29.90", narrative)
        self.assertNotIn("29.90", item["justification"])
        self.assertIn("[TEC]", narrative)
        self.assertIn("Produit analyse", narrative)
        self.assertEqual(item.get("hs_code"), "4202.91")
        self.assertIn("critere discriminant TEC", narrative)


if __name__ == "__main__":
    unittest.main()
