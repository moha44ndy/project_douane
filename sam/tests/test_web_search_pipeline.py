"""Verifie que la recherche internet precede la classification TEC dans le pipeline."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sam.product_identification import prepare_query_for_classification
from sam.rag import ClassificationPipelineResult, process_user_input


class TestWebSearchPipelineOrder(unittest.TestCase):
    @patch("sam.rag.use_llm")
    @patch("sam.product_identification.identify_with_openai_web_search")
    @patch("sam.product_identification.openai_web_search_enabled", return_value=True)
    @patch("sam.product_identification.product_identification_enabled", return_value=True)
    def test_web_search_runs_before_classification_llm(
        self,
        _prod_enabled,
        _web_enabled,
        mock_web_search,
        mock_use_llm,
    ) -> None:
        call_log: list[str] = []

        def _web(*, instructions: str, user_input: str):
            call_log.append("web_search")
            return (
                '{"product_name":"Siemens HMI","product_type":"panneau operateur",'
                '"function_usage":"interface homme-machine industrielle",'
                '"materials":["plastique","verre"],'
                '"technical_characteristics":["ecran tactile"],'
                '"missing_for_customs":[],"identification_confidence":85,'
                '"enriched_description":"Produit : Siemens HMI\\nUsage : automate",'
                '"notes":""}',
                [{"title": "Siemens", "url": "https://example.com/siemens", "snippet": ""}],
                ["6AV2124-0QC02-0AX"],
            )

        def _classify(_prompt: str):
            call_log.append("classification_llm")
            return '{"narrative":"","classifications":[]}'

        mock_web_search.side_effect = _web
        mock_use_llm.side_effect = _classify

        chunks = [MagicMock(page_content="8524 appareils automatiques")]
        index = MagicMock()
        index.search.return_value = ([[0]], [[0.0]])

        with patch("sam.rag.search_faiss_index", return_value=([0], [0.0])):
            with patch(
                "sam.rag.retrieve_locked_tec_context",
                return_value=(
                    "POSITIONS TEC CANDIDATES (VERROUILLAGE OBLIGATOIRE):\n1. Position 85.24",
                    [{"position_code": "85.24", "label": "Circuits", "score": 1.0, "matched_codes": []}],
                ),
            ):
                result = process_user_input("6AV2124-0QC02-0AX", chunks, index)

        self.assertIsInstance(result, ClassificationPipelineResult)
        self.assertEqual(call_log, ["web_search", "classification_llm"])
        self.assertTrue(result.product_identifications)
        self.assertTrue(result.product_identifications[0].get("web_search_used"))
        self.assertTrue(result.product_identifications[0].get("tec_position_candidates"))

        llm_prompt = mock_use_llm.call_args[0][0]
        self.assertIn("VERROUILLAGE OBLIGATOIRE", llm_prompt)
        self.assertIn("Complement internet", llm_prompt)
        self.assertIn("https://example.com/siemens", llm_prompt)
        self.assertIn("Description enrichie pour classification", llm_prompt)

    @patch("sam.product_identification.identify_with_openai_web_search")
    @patch("sam.product_identification.openai_web_search_enabled", return_value=True)
    @patch("sam.product_identification.product_identification_enabled", return_value=True)
    def test_structured_dossier_skips_web_search(
        self,
        _prod_enabled,
        _web_enabled,
        mock_web_search,
    ) -> None:
        dossier = """Produit : Sac a dos
Composition :
- 45 % polyester
Usage :
Randonnee"""
        text, identification = prepare_query_for_classification(dossier)
        self.assertEqual(text, dossier)
        self.assertTrue(identification.skipped)
        mock_web_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
