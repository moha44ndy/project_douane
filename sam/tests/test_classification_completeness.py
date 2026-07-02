import unittest

from sam.classification_completeness import (
    analyze_classification_completeness,
    apply_completeness_adjustments,
)
from sam.classification_risk import assess_contestation_risk
from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index
from sam.tariff_position_rules import (
    build_surface_sensitive_positions,
    set_surface_sensitive_positions,
)

BACKPACK = """Produit : Sac a dos de randonnee

Composition :
- 45 % polyester
- 30 % cuir bovin
- 20 % nylon
- 5 % aluminium (armature)

Usage :
Transport de materiel de randonnee.

Capacite :
45 litres."""

BACKPACK_WITH_EXTERIOR = BACKPACK + "\n\nSurface exterieure :\n100 % cuir bovin apparent."


class TestClassificationCompleteness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sample = type(
            "Doc",
            (),
            {
                "page_content": (
                    "42.02 -- Sacs a main et contenants similaires, a surface exterieure en cuir\n"
                    "4202.92.90.00 -- Sacs a dos -- A surface exterieure en cuir naturel kg 20 1"
                )
            },
        )()
        label_index = build_tariff_label_index([sample])
        set_tariff_label_index(label_index)
        set_surface_sensitive_positions(build_surface_sensitive_positions(label_index))

    def test_mixed_backpack_requires_exterior_surface(self) -> None:
        analysis = analyze_classification_completeness(
            source_text=BACKPACK,
            item={
                "hs_code": "4202.22.90.00",
                "chapter": "42",
                "description": "Sac a dos de randonnee",
                "confidence": 90,
            },
        )
        self.assertEqual(analysis["classification_status"], "provisoire")
        self.assertTrue(analysis["requires_exterior_surface"])
        self.assertIn("Surface exterieure", analysis["missing_critical"][0])

    def test_exterior_surface_allows_confirmed_status(self) -> None:
        analysis = analyze_classification_completeness(
            source_text=BACKPACK_WITH_EXTERIOR,
            item={
                "hs_code": "4202.91.90.00",
                "chapter": "42",
                "description": "Sac a dos de randonnee",
                "confidence": 90,
            },
        )
        self.assertEqual(analysis["classification_status"], "confirmee")
        self.assertFalse(analysis["requires_exterior_surface"])

    def test_apply_completeness_caps_confidence(self) -> None:
        item = {
            "hs_code": "4202.22.90.00",
            "chapter": "42",
            "description": "Sac a dos de randonnee",
            "confidence": 90,
            "justification": "RGI 3 : predominance cuir. Codes 4202.31 (cuir) ou 4202.32 (textile).",
        }
        apply_completeness_adjustments(item, source_text=BACKPACK)
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(item["confidence"], 65)
        self.assertEqual(item["hs_code"], "42.02")
        self.assertEqual(item["hs_code_suggested"], "4202.22.90.00")
        self.assertEqual(item["subposition_status"], "a_determiner")
        self.assertIn("surface exterieure", item["justification"].lower())
        self.assertNotIn("4202.31", item["justification"])
        self.assertNotIn("sac a dos releve", item["justification"].lower())
        self.assertIn("classification_analysis", item)
        self.assertEqual(item["classification_analysis"]["chapter_retained"], "42")

    def test_confirmed_backpack_keeps_full_code(self) -> None:
        item = {
            "hs_code": "4202.91.90.00",
            "chapter": "42",
            "description": "Sac a dos de randonnee",
            "confidence": 90,
        }
        apply_completeness_adjustments(item, source_text=BACKPACK_WITH_EXTERIOR)
        self.assertEqual(item["classification_status"], "confirmee")
        self.assertEqual(item["hs_code"], "4202.91.90.00")
        self.assertNotIn("subposition_status", item)

    def test_llm_surface_hallucination_still_flags_missing(self) -> None:
        analysis = analyze_classification_completeness(
            source_text=BACKPACK,
            item={
                "hs_code": "4202.92.00.00",
                "chapter": "42",
                "description": "Sac a dos avec surface exterieure mixte polyester et cuir",
                "confidence": 65,
            },
        )
        self.assertEqual(analysis["classification_status"], "provisoire")
        self.assertTrue(analysis["requires_exterior_surface"])

    def test_sanitize_removes_hallucinated_surface_from_description(self) -> None:
        item = {
            "hs_code": "4202.92.00.00",
            "chapter": "42",
            "description": (
                "Sac a dos de randonnee, surface exterieure mixte polyester, cuir et nylon, "
                "avec armature aluminium, capacite 45 litres"
            ),
            "confidence": 65,
            "justification": "RGI 3 b appliquee : surface exterieure mixte.",
        }
        apply_completeness_adjustments(item, source_text=BACKPACK)
        self.assertNotIn("surface exterieure mixte", item["description"].lower())
        self.assertIn("randonnee", item["description"].lower())
        self.assertIn("RGI 3 non applicable", item["justification"])
        self.assertNotIn("RGI 3 b", item["justification"])

    def test_sanitize_narrative_uses_canonical_ch42_text(self) -> None:
        from sam.classification_completeness import sanitize_provisional_narrative

        cleaned = sanitize_provisional_narrative(
            "RGI 3 b appliquee : matiere de la surface exterieure mixte.",
            [
                {
                    "requires_exterior_surface": True,
                    "description": "Sac a dos de randonnee",
                    "hs_code": "42.02",
                    "chapter": "42",
                }
            ],
        )
        self.assertIn("42.02", cleaned)
        self.assertNotIn("matiere de la,", cleaned.lower())
        self.assertEqual(cleaned.count("RGI 3 non applicable"), 1)

    def test_description_rebuilt_with_composition_from_source(self) -> None:
        item = {
            "hs_code": "4202.92.00.00",
            "chapter": "42",
            "description": "Sac a dos de randonnee en polyester, cuir bovin, nylon et aluminium",
            "confidence": 65,
        }
        apply_completeness_adjustments(item, source_text=BACKPACK)
        self.assertIn("Sac a dos de randonnee", item["description"])
        self.assertIn("45 % polyester", item["description"])
        self.assertIn("composition mixte", item["description"].lower())
        self.assertNotIn("Usage :", item["description"])
        self.assertEqual(item.get("product_name"), "Sac a dos de randonnee")

    def test_narrative_uses_product_name_only(self) -> None:
        from sam.classification_completeness import build_provisional_ch42_narrative

        narrative = build_provisional_ch42_narrative(
            [
                {
                    "requires_exterior_surface": True,
                    "product_name": "Sac a dos de randonnee",
                    "description": (
                        "Sac a dos de randonnee — composition mixte (45 % polyester) — "
                        "transport de materiel — capacite 45 litres"
                    ),
                }
            ]
        )
        self.assertIn("Produit analyse\nSac a dos de randonnee", narrative)
        self.assertNotIn("Pour Sac a dos", narrative)

    def test_inline_dossier_single_line_description_and_narrative(self) -> None:
        from sam.classification_completeness import build_provisional_ch42_narrative

        inline = (
            "Produit : Sac a dos de randonnee Composition : - 45 % polyester - 30 % cuir "
            "Usage : Transport de materiel. Capacite : 45 litres."
        )
        item = {
            "hs_code": "4202.92.00.00",
            "chapter": "42",
            "description": inline,
            "confidence": 65,
        }
        apply_completeness_adjustments(item, source_text=inline)
        self.assertEqual(item.get("product_name"), "Sac a dos de randonnee")
        self.assertIn("composition mixte", item["description"].lower())
        self.assertNotIn("Usage :", item["description"])
        narrative = build_provisional_ch42_narrative([item])
        self.assertIn("Produit analyse\nSac a dos de randonnee", narrative)
        self.assertNotIn("45 % polyester", narrative)

    def test_risk_provisoire_is_yellow_not_red(self) -> None:
        item = {
            "hs_code": "4202.22.90.00",
            "chapter": "42",
            "description": "Sac a dos de randonnee",
            "confidence": 65,
            "classification_status": "provisoire",
            "missing_fields": ["Surface exterieure (matiere apparente, selon libelle TEC)"],
            "position_label": "Autres",
        }
        risk = assess_contestation_risk(item)
        self.assertEqual(risk["risk_level"], "medium")
        self.assertIn("insuffisante", risk["risk_label"])


if __name__ == "__main__":
    unittest.main()
