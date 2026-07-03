import unittest
from unittest.mock import patch

from sam.openai_web_search import (
    _extract_output_text,
    extract_url_citations,
    openai_web_search_enabled,
)


class TestOpenAIWebSearch(unittest.TestCase):
    def test_extract_output_text_from_output_array(self) -> None:
        data = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"product_name":"Siemens HMI"}',
                            "annotations": [],
                        }
                    ],
                }
            ]
        }
        self.assertIn("Siemens HMI", _extract_output_text(data))

    def test_extract_url_citations(self) -> None:
        data = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Panel industriel",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/spec",
                                    "title": "Fiche produit",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        sources = extract_url_citations(data)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["url"], "https://example.com/spec")
        self.assertEqual(sources[0]["title"], "Fiche produit")

    def test_extract_web_search_queries(self) -> None:
        data = {
            "output": [
                {
                    "type": "web_search_call",
                    "action": {"type": "search", "query": "6AV2124-0QC02-0AX"},
                }
            ]
        }
        from sam.openai_web_search import extract_web_search_queries

        self.assertEqual(extract_web_search_queries(data), ["6AV2124-0QC02-0AX"])

    def test_openai_web_search_disabled_without_api_key(self) -> None:
        with patch("sam.openai_web_search.Config.OPENAI_API_KEY", None):
            self.assertFalse(openai_web_search_enabled())


if __name__ == "__main__":
    unittest.main()
