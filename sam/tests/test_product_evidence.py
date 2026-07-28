from __future__ import annotations

import unittest
from unittest.mock import patch

from sam.functional_profile import build_functional_profile
from sam.product_evidence import build_product_evidence


class TestProductEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self._fallback_patch = patch(
            "sam.functional_profile._llm_fallback_enabled",
            return_value=False,
        )
        self._fallback_patch.start()

    def tearDown(self) -> None:
        self._fallback_patch.stop()

    def test_builds_typed_evidence_from_web_identification(self) -> None:
        source = "Produit : REF-100\nReference fabricant : REF-100"
        identification = {
            "skipped": False,
            "input_type": "manufacturer_ref",
            "product_name": "REF-100",
            "product_type": "industrial data controller",
            "manufacturer": "Example",
            "manufacturer_part_number": "REF-100",
            "function_usage": "control and exchange industrial data",
            "technical_characteristics": ["Ethernet interface", "24 V DC"],
            "missing_for_customs": ["standalone or component"],
            "identification_confidence": 88,
            "identification_method": "web_search",
            "web_search_used": True,
            "web_sources": [{"url": "https://example.com/ref-100"}],
        }
        profile = build_functional_profile(source, identification)

        evidence = build_product_evidence(source, identification, profile)

        self.assertEqual(evidence.identification_status, "identified")
        self.assertEqual(evidence.manufacturer_reference, "REF-100")
        self.assertEqual(evidence.identity_confidence, 88)
        self.assertIn("Ethernet interface", evidence.characteristics)
        self.assertIn("web_search", evidence.evidence_sources)
        self.assertEqual(evidence.source_urls, ["https://example.com/ref-100"])
        self.assertIn("Example", evidence.identity_terms)
        self.assertIn("REF-100", evidence.retrieval_query())
        self.assertNotIn("hs_code", evidence.to_dict())

    def test_uncertain_identity_is_explicit_and_prompt_requires_provisional_result(self) -> None:
        identification = {
            "skipped": False,
            "product_name": "Unknown X1",
            "product_type": "electronic module",
            "identification_unstable": True,
            "identification_confidence": 42,
        }
        profile = build_functional_profile("Unknown X1", identification)

        evidence = build_product_evidence("Unknown X1", identification, profile)

        self.assertEqual(evidence.identification_status, "uncertain")
        self.assertEqual(evidence.identity_confidence, 42)
        self.assertIn("identification incertaine", evidence.ambiguity_flags)
        self.assertIn("provisoire", evidence.prompt_block())

    def test_retrieval_query_excludes_price_and_origin(self) -> None:
        source = (
            "Produit : Module reseau\nUsage : transmettre des donnees\n"
            "Caracteristiques : 4 ports Ethernet\nOrigine : Chine\nValeur : 500 USD"
        )
        identification = {"skipped": True, "identification_confidence": 100}
        profile = build_functional_profile(source, identification)

        query = build_product_evidence(source, identification, profile).retrieval_query()

        self.assertIn("transmettre des donnees", query)
        self.assertNotIn("500", query)
        self.assertNotIn("Chine", query)

    def test_reference_without_confirmed_identity_sets_ambiguity_flag(self) -> None:
        identification = {
            "skipped": False,
            "input_type": "manufacturer_ref",
            "product_name": "ABC-123",
            "product_type": "electronic module",
            "manufacturer_part_number": "ABC-123",
            "identification_confidence": 48,
            "identification_unstable": True,
        }
        profile = build_functional_profile("Produit : ABC-123\nReference fabricant : ABC-123", identification)

        evidence = build_product_evidence("Produit : ABC-123\nReference fabricant : ABC-123", identification, profile)

        self.assertIn(
            "reference fabricant non rattachee a un produit confirme",
            evidence.ambiguity_flags,
        )


if __name__ == "__main__":
    unittest.main()
