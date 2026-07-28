from __future__ import annotations

import unittest
from unittest.mock import patch

from sam.functional_coherence import (
    apply_functional_coherence_gate,
    check_functional_coherence,
    enforce_functional_coherence_cap,
)


class TestFunctionalCoherence(unittest.TestCase):
    def setUp(self) -> None:
        self._fallback_patch = patch(
            "sam.functional_profile._llm_fallback_enabled",
            return_value=False,
        )
        self._fallback_patch.start()

    def tearDown(self) -> None:
        self._fallback_patch.stop()

    @patch("sam.functional_coherence.list_subpositions_for_position")
    @patch("sam.functional_coherence.get_position_heading")
    def test_incompatible_exact_label_is_downgraded_without_code_replacement(
        self,
        heading,
        subpositions,
    ) -> None:
        heading.return_value = "Telephone equipment and smartphones"
        subpositions.return_value = [
            ("8517.13", "Smartphones"),
            ("8517.62", "Equipment for switching and transmission of data"),
        ]
        item = {
            "hs_code": "8517.13.00.00",
            "position_label": "Smartphones",
            "confidence": 95,
            "classification_status": "confirmee",
            "tec_position_candidates": [{"position_code": "85.17", "label": "Telephone equipment"}],
        }
        prod_id = {
            "functional_profile": {
                "product_type": "ethernet data switch",
                "primary_function": "switching and transmission of data",
                "characteristics": "48 ethernet ports",
            }
        }

        changed = apply_functional_coherence_gate(item, prod_id)

        self.assertTrue(changed)
        self.assertEqual(item["hs_code"], "8517.13.00.00")
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(item["confidence"], 50)
        self.assertEqual(item["functional_coherence"]["suggested_candidate"], "8517.62")

    @patch("sam.functional_coherence.list_subpositions_for_position", return_value=[])
    def test_compatible_function_is_not_downgraded(self, _subpositions) -> None:
        item = {
            "hs_code": "8504.40.00.00",
            "position_label": "Static converters",
            "confidence": 85,
            "classification_status": "confirmee",
            "tec_position_candidates": [],
        }
        prod_id = {
            "functional_profile": {
                "product_type": "static converter",
                "primary_function": "convert electrical power",
            }
        }

        self.assertFalse(apply_functional_coherence_gate(item, prod_id))
        self.assertEqual(item["classification_status"], "confirmee")

    def test_blank_code_becomes_explicit_unresolved_result(self) -> None:
        item = {"hs_code": "", "confidence": 95, "classification_status": "confirmee"}

        changed = apply_functional_coherence_gate(item, {"skipped": True})

        self.assertTrue(changed)
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(item["confidence"], 40)
        self.assertEqual(item["functional_coherence"]["status"], "unresolved")

    @patch("sam.functional_coherence.list_subpositions_for_position", return_value=[])
    def test_complete_storage_system_is_not_accepted_as_recording_media(self, _subpositions) -> None:
        item = {
            "hs_code": "8523",
            "position_label": "Disques bandes cartes et autres supports pour enregistrement",
            "confidence": 90,
            "classification_status": "confirmee",
            "tec_position_candidates": [{"position_code": "85.23", "label": "Supports"}],
        }
        prod_id = {
            "functional_profile": {
                "product_type": "data storage array",
                "primary_function": "store and administer data",
                "characteristics": "complete enterprise storage system",
                "system_role": "standalone_system",
                "semantic_terms": ["storage", "system", "unit", "data"],
            }
        }

        self.assertTrue(apply_functional_coherence_gate(item, prod_id))
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertEqual(item["functional_coherence"]["status"], "incompatible")

    @patch("sam.functional_coherence.list_subpositions_for_position", return_value=[])
    def test_digital_ip_camera_is_not_accepted_as_cinematographic_camera(
        self,
        _subpositions,
    ) -> None:
        item = {
            "hs_code": "9007.10.00.00",
            "position_label": "Cameras cinematographiques",
            "source_query": (
                "Produit : Camera IP thermique\n"
                "Usage : Imagerie video numerique et surveillance reseau"
            ),
            "confidence": 95,
            "classification_status": "confirmee",
            "tec_position_candidates": [],
        }

        self.assertTrue(apply_functional_coherence_gate(item, {"skipped": True}))
        self.assertEqual(item["functional_coherence"]["status"], "incompatible")
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertLessEqual(item["confidence"], 50)

    @patch("sam.functional_coherence.list_subpositions_for_position", return_value=[])
    def test_tablet_is_not_accepted_as_smartphone(self, _subpositions) -> None:
        item = {
            "hs_code": "8517.13.00.00",
            "position_label": "Smartphones",
            "source_query": "Produit : Tablette tactile\nUsage : Traitement de donnees",
            "confidence": 95,
            "classification_status": "confirmee",
            "tec_position_candidates": [],
        }

        self.assertTrue(apply_functional_coherence_gate(item, {"skipped": True}))
        self.assertEqual(item["functional_coherence"]["status"], "incompatible")

    @patch("sam.functional_coherence.list_subpositions_for_position", return_value=[])
    def test_medical_syringe_is_not_accepted_as_radiology_equipment(self, _subpositions) -> None:
        item = {
            "hs_code": "9022.14.00.00",
            "position_label": "Appareils a rayons X pour usages medicaux",
            "source_query": "Produit : Disposable medical syringe\nUsage : Injection sterile a usage medical",
            "confidence": 95,
            "classification_status": "confirmee",
            "tec_position_candidates": [],
        }

        self.assertTrue(apply_functional_coherence_gate(item, {"skipped": True}))
        self.assertEqual(item["functional_coherence"]["status"], "incompatible")
        self.assertEqual(item["classification_status"], "provisoire")

    def test_invalid_item_returns_no_result(self) -> None:
        self.assertIsNone(check_functional_coherence("not-a-dict", None))

    def test_final_cap_restores_provisional_status_after_later_stage(self) -> None:
        item = {
            "functional_coherence": {"status": "incompatible"},
            "classification_status": "confirmee",
            "confidence": 92,
            "classification_confidence": 88,
        }

        self.assertTrue(enforce_functional_coherence_cap(item))
        self.assertEqual(item["classification_status"], "provisoire")
        self.assertEqual(item["confidence"], 50)
        self.assertEqual(item["classification_confidence"], 50)


if __name__ == "__main__":
    unittest.main()
