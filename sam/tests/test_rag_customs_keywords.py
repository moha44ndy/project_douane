"""Regression tests for zero-cost structured-product TEC vocabulary."""

from __future__ import annotations

import unittest

from sam.rag import (
    _CLASSIFICATION_OUTPUT_CONTRACT,
    _build_heading_hint_phrases,
    _build_customs_label_keywords,
    split_user_queries,
)


class TestStructuredCustomsKeywords(unittest.TestCase):
    def test_output_contract_contains_no_fixed_tariff_answer(self) -> None:
        self.assertNotIn("8517.13", _CLASSIFICATION_OUTPUT_CONTRACT)
        self.assertNotRegex(_CLASSIFICATION_OUTPUT_CONTRACT, r"\b\d{4}\.\d{2}\b")
        self.assertIn("aucun code d'exemple", _CLASSIFICATION_OUTPUT_CONTRACT)
        self.assertIn("450 caracteres max", _CLASSIFICATION_OUTPUT_CONTRACT)
        self.assertIn("il ne doit jamais etre vide", _CLASSIFICATION_OUTPUT_CONTRACT)

    def test_multiple_structured_dossiers_are_split_before_candidate_retrieval(self) -> None:
        dossiers = [
            "Produit : Stainless steel vacuum flask\nComposition : acier\nUsage : boisson",
            "Produit : LED household light bulb\nComposition : aluminium\nUsage : eclairage",
            "Produit : Polypropylene woven packing sack\nComposition : polypropylene\nUsage : emballage",
        ]
        self.assertEqual(split_user_queries("\n\n".join(dossiers)), dossiers)

    def test_vacuum_flask_maps_to_isothermal_heading_terms(self) -> None:
        keywords = _build_customs_label_keywords(
            "Stainless steel vacuum flask with double wall", "", ""
        )
        self.assertIn("bouteilles isolantes", keywords)
        self.assertIn("recipients isothermiques", keywords)

    def test_led_bulb_maps_to_electric_lamp_terms(self) -> None:
        keywords = _build_customs_label_keywords(
            "LED household light bulb E27 12 W", "", ""
        )
        self.assertIn("lampes", keywords)
        self.assertIn("diodes", keywords)
        self.assertIn("emettrices", keywords)

    def test_woven_packing_sack_maps_to_packaging_sack_terms(self) -> None:
        keywords = _build_customs_label_keywords(
            "Polypropylene woven packing sack for agricultural products", "", ""
        )
        self.assertIn("sacs", keywords)
        self.assertIn("sachets", keywords)
        self.assertIn("emballage", keywords)

    def test_medical_syringe_maps_to_medical_instrument_terms(self) -> None:
        keywords = _build_customs_label_keywords(
            "Disposable medical syringe",
            "Inject sterile liquid for medical use",
            "",
        )
        self.assertIn("seringues", keywords)
        self.assertIn("aiguilles", keywords)
        self.assertIn("medicaux", keywords)

    def test_unrelated_product_does_not_get_targeted_aliases(self) -> None:
        keywords = _build_customs_label_keywords(
            "Wooden office writing desk with drawers", "", ""
        )
        self.assertNotIn("diodes", keywords)
        self.assertNotIn("recipients isothermiques", keywords)
        self.assertNotIn("sachets", keywords)

    def test_tablet_promotes_data_processing_terms_not_smartphone_terms(self) -> None:
        keywords = _build_customs_label_keywords(
            "Mobile tablet computer",
            "Portable data processing with touchscreen",
            "computing device",
        )

        self.assertIn("traitement", keywords)
        self.assertIn("information", keywords)
        self.assertIn("machines", keywords)
        self.assertIn("automatiques", keywords)
        self.assertNotIn("intelligent", keywords)

    def test_modern_camera_promotes_digital_camera_terms(self) -> None:
        keywords = _build_customs_label_keywords(
            "IP thermal camera",
            "Digital video surveillance and imaging",
            "network camera",
        )

        self.assertIn("photographiques", keywords)
        self.assertIn("numeriques", keywords)
        self.assertIn("camescopes", keywords)
        self.assertIn("television", keywords)

    def test_cinematographic_camera_does_not_get_modern_camera_aliases(self) -> None:
        keywords = _build_customs_label_keywords(
            "Cinematographic film camera",
            "Record motion pictures on film",
            "cinema equipment",
        )

        self.assertNotIn("numeriques", keywords)

    def test_capability_natures_expand_to_official_label_vocabulary(self) -> None:
        cases = [
            (
                "complete data storage system or storage unit",
                {"unites", "memoire", "stockage", "machines", "automatiques"},
            ),
            (
                "programmable industrial control equipment",
                {"commande", "panneau"},
            ),
            (
                "industrial robot",
                {"robots", "industriels"},
            ),
            (
                "data processing accelerator or expansion card",
                {"parties", "accessoires", "traitement"},
            ),
            (
                "static electrical power converter or variable speed drive",
                {"convertisseur", "statique", "moteur"},
            ),
        ]
        for nature, expected in cases:
            with self.subTest(nature=nature):
                keywords = set(_build_customs_label_keywords(nature, "", ""))
                self.assertTrue(expected.issubset(keywords))

    def test_tablet_heading_hints_include_adp_family(self) -> None:
        hints = _build_heading_hint_phrases(
            "portable tablet or hybrid data processing computer",
            "execute office and multimedia applications",
            "",
        )

        joined = " ".join(hints)
        self.assertIn("machines automatiques de traitement de l information", joined)

    def test_converter_heading_hints_include_static_converter_family(self) -> None:
        hints = _build_heading_hint_phrases(
            "static electrical power converter or variable speed drive",
            "regulate the speed of an electric motor",
            "",
        )

        joined = " ".join(hints)
        self.assertIn("convertisseurs electriques statiques", joined)


if __name__ == "__main__":
    unittest.main()
