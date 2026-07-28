import unittest
from unittest.mock import patch

from sam.product_identification import (
    InputType,
    ProductIdentification,
    _normalize_identification_output,
    description_is_already_rich,
    identify_product,
    looks_like_structured_dossier,
    prepare_query_for_classification,
    should_use_web_search_for_identification,
    should_run_product_identification,
)


class TestProductIdentification(unittest.TestCase):
    def test_structured_dossier_skips_agent(self) -> None:
        text = (
            "Produit : Sac a dos\nComposition :\n- 45 % polyester\nUsage :\nRandonnee"
        )
        self.assertTrue(looks_like_structured_dossier(text))
        self.assertFalse(should_run_product_identification(text))

    def test_short_product_name_triggers_agent(self) -> None:
        with patch("sam.product_identification.product_identification_enabled", return_value=True):
            self.assertTrue(should_run_product_identification("MacBook Pro M4"))

    @patch("sam.product_identification.product_identification_enabled", return_value=True)
    @patch("sam.product_identification._call_with_optional_web")
    @patch("sam.product_identification.cache_set")
    @patch("sam.product_identification.cache_get", return_value=None)
    def test_identify_product_builds_enriched_dossier(
        self,
        _cache_get,
        _cache_set,
        mock_call,
        _enabled,
    ) -> None:
        mock_call.return_value = (
            (
                '{"product_name":"Nike Air Force 1 Low","product_type":"chaussure de sport",'
                '"function_usage":"chaussure de ville et sport",'
                '"materials":["tige cuir","semelle caoutchouc"],'
                '"technical_characteristics":["basket montante"],'
                '"missing_for_customs":["poids net"],'
                '"identification_confidence":82,'
                '"identification_method":"connaissance generale",'
                '"reasoning":"Chaussure Nike emblematique",'
                '"enriched_description":"Produit : Nike Air Force 1 Low\\nUsage : chaussure",'
                '"notes":""}'
            ),
            [{"title": "Nike", "url": "https://example.com/nike", "snippet": ""}],
            ["Nike Air Force 1 Low"],
            True,
            False,
        )
        result = identify_product("Nike Air Force 1 Low")
        self.assertEqual(result.product_name, "Nike Air Force 1 Low")
        self.assertIn("chaussure", result.enriched_description.lower())
        self.assertGreaterEqual(result.identification_confidence, 80)
        self.assertTrue(result.web_search_used)
        self.assertEqual(result.web_sources[0]["url"], "https://example.com/nike")
        self.assertNotIn("8471", result.enriched_description)
        self.assertFalse(result.web_search_failed)

    @patch("sam.product_identification.should_run_product_identification", return_value=False)
    def test_prepare_query_passthrough_when_not_needed(self, _should) -> None:
        query = "Produit : Sac\nComposition :\n- 50 % cuir\nUsage :\nville"
        text, identification = prepare_query_for_classification(query)
        self.assertEqual(text, query)
        self.assertTrue(identification.skipped)

    def test_rich_description_skips_agent(self) -> None:
        rich = (
            "Chaussure de securite en cuir et textile, semelle caoutchouc, "
            "coquille metal, usage industriel, norme EN ISO 20345, destinee au chantier"
        )
        self.assertTrue(description_is_already_rich(rich))

    @patch("sam.product_identification.openai_web_search_enabled", return_value=True)
    def test_web_search_policy_auto_uses_web_for_manufacturer_refs(self, _enabled) -> None:
        self.assertTrue(
            should_use_web_search_for_identification("6AV2124-0QC02-0AX0", "manufacturer_ref")
        )

    @patch("sam.product_identification.openai_web_search_enabled", return_value=True)
    def test_web_search_policy_auto_skips_web_for_rich_descriptions(self, _enabled) -> None:
        rich = (
            "Chaussure de securite en cuir et textile, semelle caoutchouc, "
            "coquille metal, usage industriel, norme EN ISO 20345, destinee au chantier"
        )
        self.assertFalse(
            should_use_web_search_for_identification(rich, "free_description")
        )

    @patch("sam.product_identification.should_run_product_identification", return_value=True)
    @patch("sam.product_identification.cache_get")
    def test_identify_product_uses_cache_before_llm(self, mock_cache_get, _should) -> None:
        mock_cache_get.return_value = (
            '{"original_query":"iPhone 15","input_type":"commercial_name","product_name":"iPhone 15",'
            '"product_type":"smartphone","family":"","manufacturer":"Apple","manufacturer_part_number":"",'
            '"commercial_name":"iPhone 15","function_usage":"telephone mobile","why_not_other_products":"",'
            '"materials":[],"technical_characteristics":[],"missing_for_customs":[],"identification_confidence":91,'
            '"identification_method":"cache","reasoning":"cached","enriched_description":"Produit : iPhone 15",'
            '"notes":"","web_search_used":false,"web_search_failed":false,"web_sources":[],"web_search_queries":[],'
            '"identification_unstable":false,"skipped":false,"skip_reason":"","attempt_count":1}'
        )
        with patch("sam.product_identification._call_with_optional_web") as mock_call:
            result = identify_product("iPhone 15")
        self.assertEqual(result.product_name, "iPhone 15")
        mock_call.assert_not_called()

    def test_normalize_identification_output_strengthens_reference_uncertainty(self) -> None:
        identification = ProductIdentification(
            original_query="6ES7214-1AG40-0XB0",
            input_type=InputType.MANUFACTURER_REF,
            product_name="6ES7214-1AG40-0XB0",
            product_type="electronic module",
            function_usage="industrial use",
            identification_confidence=82,
            enriched_description="Produit : Siemens module",
        )

        normalized = _normalize_identification_output(
            "6ES7214-1AG40-0XB0",
            identification,
        )

        self.assertEqual(normalized.manufacturer_part_number, "6ES7214-1AG40-0XB0")
        self.assertIn("Reference fabricant", normalized.enriched_description)
        self.assertLessEqual(normalized.identification_confidence, 55)
        self.assertIn("type de produit exact a confirmer", normalized.missing_for_customs)
        self.assertIn("fonction principale exacte a confirmer", normalized.missing_for_customs)

    def test_normalize_identification_output_preserves_strong_specific_result(self) -> None:
        identification = ProductIdentification(
            original_query="Cisco C9200L-48P-4X-E",
            input_type=InputType.MANUFACTURER_REF,
            product_name="Cisco Catalyst 9200L",
            product_type="network switch",
            function_usage="switch ethernet data traffic",
            manufacturer="Cisco",
            manufacturer_part_number="C9200L-48P-4X-E",
            technical_characteristics=["48 ports ethernet", "layer 3"],
            identification_confidence=88,
            enriched_description="Produit : Cisco Catalyst 9200L",
        )

        normalized = _normalize_identification_output(
            "Cisco C9200L-48P-4X-E",
            identification,
        )

        self.assertEqual(normalized.identification_confidence, 88)
        self.assertIn("48 ports ethernet", normalized.technical_characteristics)
        self.assertNotIn("type de produit exact a confirmer", normalized.missing_for_customs)


if __name__ == "__main__":
    unittest.main()
