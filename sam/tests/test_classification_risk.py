import unittest

from sam.classification_risk import assess_contestation_risk


class TestClassificationRisk(unittest.TestCase):
    def test_low_risk_complete_case(self) -> None:
        risk = assess_contestation_risk(
            {
                "hs_code": "4202.31.00.00",
                "position_label": "Sacs a main en cuir",
                "description": "Sac a main en cuir de crocodile, doublure coton, fermeture metallique",
                "confidence": 92,
                "quantity_confidence": 80,
                "origin": "France",
                "value": "22000 USD",
            }
        )
        self.assertEqual(risk["risk_level"], "low")
        self.assertIn("Faible risque", risk["risk_label"])

    def test_low_risk_even_when_quantity_confidence_is_default(self) -> None:
        """quantity_confidence=60 par defaut ne doit pas declencher description incomplete."""
        risk = assess_contestation_risk(
            {
                "hs_code": "4202.31.00.00",
                "position_label": "Sacs a main en cuir",
                "description": (
                    "Sac a main de luxe a surface exterieure en cuir naturel de crocodile, "
                    "destine au transport d'effets personnels"
                ),
                "confidence": 96,
                "quantity_confidence": 60,
                "origin": "France",
                "value": "22000 USD",
            }
        )
        self.assertEqual(risk["risk_level"], "low")

    def test_low_risk_with_high_description_quality(self) -> None:
        risk = assess_contestation_risk(
            {
                "hs_code": "4202.31.00.00",
                "position_label": "Sacs a main en cuir",
                "description": "Sac a main",
                "confidence": 95,
                "description_quality": 100,
            }
        )
        self.assertEqual(risk["risk_level"], "low")

    def test_medium_risk_when_description_is_vague(self) -> None:
        risk = assess_contestation_risk(
            {
                "hs_code": "8517.13.00.00",
                "position_label": "Telephones intelligents",
                "description": "appareil electronique portable",
                "confidence": 75,
                "quantity_confidence": 60,
            }
        )
        self.assertEqual(risk["risk_level"], "medium")
        self.assertIn("incomplète", risk["risk_label"])

    def test_high_risk_when_hs_missing(self) -> None:
        risk = assess_contestation_risk(
            {
                "hs_code": "Non renseigne",
                "description": "Produit inconnu",
                "confidence": 20,
                "quantity_confidence": 40,
            }
        )
        self.assertEqual(risk["risk_level"], "high")
        self.assertIn("incertain", risk["risk_label"])

    def test_high_risk_when_confidence_low(self) -> None:
        risk = assess_contestation_risk(
            {
                "hs_code": "8517.13.00.00",
                "position_label": "Telephones intelligents",
                "description": "Appareil electronique portable avec ecran et batterie",
                "confidence": 50,
                "quantity_confidence": 55,
                "justification": "Classification indicative, plusieurs positions possibles.",
            }
        )
        self.assertEqual(risk["risk_level"], "high")


if __name__ == "__main__":
    unittest.main()
