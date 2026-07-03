import unittest
from unittest.mock import patch

from sam.product_identification import (
    description_is_already_rich,
    identify_product,
    looks_like_structured_dossier,
    prepare_query_for_classification,
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
    @patch("sam.product_identification._call_identification_with_optional_web")
    def test_identify_product_builds_enriched_dossier(
        self,
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
                '"enriched_description":"Produit : Nike Air Force 1 Low\\nUsage : chaussure",'
                '"notes":""}'
            ),
            [{"title": "Nike", "url": "https://example.com/nike", "snippet": ""}],
            ["Nike Air Force 1 Low"],
            True,
        )
        result = identify_product("Nike Air Force 1 Low")
        self.assertEqual(result.product_name, "Nike Air Force 1 Low")
        self.assertIn("chaussure", result.enriched_description.lower())
        self.assertGreaterEqual(result.identification_confidence, 80)
        self.assertTrue(result.web_search_used)
        self.assertEqual(result.web_sources[0]["url"], "https://example.com/nike")
        self.assertNotIn("8471", result.enriched_description)

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


if __name__ == "__main__":
    unittest.main()
