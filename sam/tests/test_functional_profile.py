from __future__ import annotations

import unittest
from unittest.mock import patch

from sam.functional_profile import build_functional_profile


class TestFunctionalProfile(unittest.TestCase):
    def setUp(self) -> None:
        self._fallback_patch = patch(
            "sam.functional_profile._llm_fallback_enabled",
            return_value=False,
        )
        self._fallback_patch.start()

    def tearDown(self) -> None:
        self._fallback_patch.stop()

    def test_builds_tariff_neutral_profile_from_structured_row(self) -> None:
        source = (
            "Produit : Network appliance X100\n"
            "Composition :\n- Electronique, acier\n"
            "Usage :\nCommuter et transmettre des donnees sur un reseau\n"
            "Caracteristiques :\n- 48 ports Ethernet, couche 3\n"
            "Origine :\nChine"
        )

        profile = build_functional_profile(source, {"skipped": True})

        self.assertEqual(profile.designation, "Network appliance X100")
        self.assertIn("transmettre des donnees", profile.primary_function)
        self.assertIn("48 ports Ethernet", profile.characteristics)
        self.assertIn("transmission", profile.semantic_terms)
        self.assertEqual(
            profile.product_type,
            "network data switching or routing equipment",
        )
        self.assertGreaterEqual(profile.technical_nature_confidence, 70)
        self.assertNotIn("8517", str(profile.to_dict()))
        self.assertIn("Fonction principale", profile.prompt_block())

    def test_identification_evidence_overrides_weaker_free_text(self) -> None:
        profile = build_functional_profile(
            "Produit : ABC-123",
            {
                "skipped": False,
                "product_name": "ABC-123",
                "product_type": "industrial controller",
                "family": "automation equipment",
                "function_usage": "control an industrial process",
                "technical_characteristics": ["digital inputs", "relay outputs"],
                "materials": ["electronics"],
                "missing_for_customs": ["rated voltage"],
                "identification_method": "web_search",
            },
        )

        self.assertEqual(profile.product_type, "industrial controller")
        self.assertEqual(profile.primary_function, "control an industrial process")
        self.assertIn("digital inputs", profile.characteristics)
        self.assertEqual(profile.missing_discriminants, ["rated voltage"])
        self.assertIn("web_search", profile.evidence_sources)

    def test_profile_does_not_map_brand_or_model_to_tariff_code(self) -> None:
        profile = build_functional_profile(
            "Produit : Cisco Catalyst 9300\nUsage :\nCommuter le trafic Ethernet",
            {"skipped": True},
        )

        serialized = str(profile.to_dict())
        self.assertIn("Cisco Catalyst 9300", serialized)
        self.assertFalse(any("hs" in key or "tariff" in key for key in profile.to_dict()))

    def test_modern_camera_profile_includes_discriminating_terms(self) -> None:
        profile = build_functional_profile(
            "Produit : Camera thermique IP\nUsage :\nImagerie video de surveillance",
            {"skipped": True},
        )

        self.assertIn("digital", profile.semantic_terms)
        self.assertIn("video", profile.semantic_terms)

    def test_tablet_profile_is_treated_as_data_processing_device(self) -> None:
        profile = build_functional_profile(
            "Produit : Tablette tactile\nUsage :\nTraitement mobile de donnees",
            {"skipped": True},
        )

        self.assertIn("computer", profile.semantic_terms)
        self.assertIn("processing", profile.semantic_terms)

    def test_optical_component_does_not_become_camera_profile(self) -> None:
        profile = build_functional_profile(
            "Produit : Module optique SFP\nUsage : Transmission par fibre optique",
            {"skipped": True},
        )

        self.assertIn("optical", profile.semantic_terms)
        self.assertNotIn("digital", profile.semantic_terms)
        self.assertNotIn("video", profile.semantic_terms)

    def test_mixed_material_does_not_become_headset_profile(self) -> None:
        profile = build_functional_profile(
            "Produit : Sac\nComposition : Materiaux mixed coton et polyester",
            {"skipped": True},
        )

        self.assertNotIn("headset", profile.semantic_terms)
        self.assertNotIn("display", profile.semantic_terms)

    def test_storage_array_is_inferred_from_capability_not_brand(self) -> None:
        profile = build_functional_profile(
            "Produit : Unknown Enterprise X\n"
            "Usage : Stocker et administrer des donnees en baie de stockage\n"
            "Caracteristiques : Systeme complet de stockage flash entreprise",
            {"skipped": True},
        )

        self.assertEqual(
            profile.product_type,
            "complete data storage system or storage unit",
        )
        self.assertIn("baie de stockage", profile.technical_nature_signals)

    def test_imaging_nature_uses_function_and_not_model_name(self) -> None:
        profile = build_functional_profile(
            "Produit : ZX-900\n"
            "Usage : Capturer des images visibles et thermiques\n"
            "Caracteristiques : Camera multisenseur portative",
            {"skipped": True},
        )

        self.assertEqual(profile.product_type, "digital video or thermal imaging camera")
        self.assertNotEqual(profile.product_type, profile.designation)

    def test_unknown_product_does_not_invent_a_technical_nature(self) -> None:
        profile = build_functional_profile(
            "Produit : Generic object\nUsage : Usage non precise",
            {"skipped": True},
        )

        self.assertEqual(profile.product_type, "unspecified product")
        self.assertLess(profile.technical_nature_confidence, 50)

    def test_low_confidence_profile_can_use_llm_fallback(self) -> None:
        with patch(
            "sam.functional_profile._needs_llm_profile_fallback",
            return_value=True,
        ), patch(
            "sam.functional_profile._call_llm_profile_fallback",
            return_value={
                "product_type": "programmable industrial control equipment",
                "family": "industrial automation",
                "primary_function": "control industrial sequences",
                "system_role": "standalone_system",
                "semantic_terms": ["industrial", "control", "programmable"],
                "technical_signals": ["plc", "controleur industriel"],
                "missing_discriminants": ["rated voltage"],
                "confidence": 78,
            },
        ):
            profile = build_functional_profile(
                "Produit : ZX-100\nCaracteristiques : automate programmable",
                {"skipped": True},
            )

        self.assertEqual(
            profile.product_type,
            "programmable industrial control equipment",
        )
        self.assertEqual(profile.family, "industrial automation")
        self.assertIn("control", profile.semantic_terms)
        self.assertIn("rated voltage", profile.missing_discriminants)
        self.assertIn("functional_profile_llm_fallback", profile.evidence_sources)

    def test_llm_fallback_is_ignored_when_weaker_than_local_profile(self) -> None:
        with patch(
            "sam.functional_profile._needs_llm_profile_fallback",
            return_value=True,
        ), patch(
            "sam.functional_profile._call_llm_profile_fallback",
            return_value={
                "product_type": "generic electronic item",
                "confidence": 30,
            },
        ):
            profile = build_functional_profile(
                "Produit : Camera thermique IP\nUsage :\nImagerie video de surveillance",
                {"skipped": True},
            )

        self.assertEqual(profile.product_type, "digital video or thermal imaging camera")
        self.assertNotIn("functional_profile_llm_fallback", profile.evidence_sources)


if __name__ == "__main__":
    unittest.main()
