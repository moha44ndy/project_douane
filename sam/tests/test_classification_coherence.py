import unittest

from sam.classification_coherence import enforce_classification_coherence
from sam.classification_risk import assess_contestation_risk
from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index
from sam.tariff_rates import PROVISIONAL_TAX_VALUE, enrich_item_tariff_rates, set_tariff_rate_index


class _Chunk:
    def __init__(self, content: str) -> None:
        self.page_content = content


class TestClassificationCoherence(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        chunks = [
            _Chunk(
                "4202.91.10.00 -- Presentes demonte importes pour l'industrie du montage kg 20 1\n"
                "4202.91.90.00 -- Autres kg 20 1\n"
                "4202.92.90.00 -- Sacs a dos -- A surface exterieure en cuir naturel kg 20 1"
            ),
        ]
        index = build_tariff_label_index(chunks)
        set_tariff_label_index(index)
        set_tariff_rate_index(
            {
                "4202.91.90.00": {"us_unit": "kg", "dd_rate": "20", "rs_rate": "1"},
                "4202.92.90.00": {"us_unit": "kg", "dd_rate": "20", "rs_rate": "1"},
            }
        )

    def test_provisional_truncates_code(self) -> None:
        item = {
            "hs_code": "4202.91.90.00",
            "classification_status": "confirmee",
            "confidence": 90,
            "justification": "RGI 1 : le sac releve de la sous-position 4202.91.90.00.",
            "subposition_resolution": {
                "status": "insufficient",
                "hs_code": "4202.91",
                "heading_code": "4202.91",
                "confidence_cap": 75,
                "missing_criteria": [
                    "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage"
                ],
            },
            "missing_fields": [
                "Etat de presentation : monte ou demonte/non monte pour l'industrie du montage"
            ],
        }
        enforce_classification_coherence(item)
        self.assertEqual(item["hs_code"], "4202.91")
        self.assertEqual(item["hs_code_suggested"], "4202.91.90.00")
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertEqual(item["subposition_status"], "a_determiner")
        self.assertLessEqual(item["confidence"], 75)

    def test_confirmed_keeps_full_code_and_boosts_confidence(self) -> None:
        item = {
            "hs_code": "4202.91.90.00",
            "classification_status": "provisoire",
            "confidence": 65,
            "justification": (
                "Information insuffisante pour determiner avec certitude la sous-position : montage."
            ),
            "subposition_resolution": {
                "status": "confirmed",
                "matched_code": "4202.91.90.00",
                "confidence_cap": 85,
            },
        }
        enforce_classification_coherence(item)
        self.assertEqual(item["hs_code"], "4202.91.90.00")
        self.assertEqual(item["classification_status"], "confirmee")
        self.assertNotIn("subposition_status", item)
        self.assertGreaterEqual(item["confidence"], 85)

    def test_provisional_taxes_and_risk_align_with_truncated_code(self) -> None:
        item = {
            "hs_code": "4202.91.90.00",
            "classification_status": "confirmee",
            "confidence": 90,
            "justification": "Code 4202.91.90.00 propose.",
            "subposition_resolution": {
                "status": "insufficient",
                "hs_code": "4202.91",
                "heading_code": "4202.91",
                "confidence_cap": 75,
                "missing_criteria": ["Etat de presentation : monte ou demonte/non monte"],
            },
            "missing_fields": ["Etat de presentation : monte ou demonte/non monte"],
        }
        enforce_classification_coherence(item)
        enrich_item_tariff_rates(item)
        risk = assess_contestation_risk(item)
        self.assertEqual(item["dd_rate"], PROVISIONAL_TAX_VALUE)
        self.assertEqual(risk["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
