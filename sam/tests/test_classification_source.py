import unittest

from sam.classification_source import (
    build_effective_classification_source,
    identification_is_trusted,
)


class TestClassificationSource(unittest.TestCase):
    def test_trusted_identification_merges_enriched_description(self) -> None:
        item = {
            "product_identification": {
                "skipped": False,
                "identification_confidence": 85,
                "enriched_description": "Produit : Sac\nComposition :\n- cuir\nUsage :\nville",
                "materials": ["tige cuir"],
                "function_usage": "chaussure de ville",
            }
        }
        text, trusted = build_effective_classification_source("Nike Air Force 1 Low", item)
        self.assertTrue(trusted)
        self.assertIn("cuir", text.lower())
        self.assertIn("chaussure", text.lower())
        self.assertTrue(identification_is_trusted(item))

    def test_low_confidence_identification_not_trusted(self) -> None:
        item = {
            "product_identification": {
                "skipped": False,
                "identification_confidence": 40,
                "enriched_description": "Produit vague",
            }
        }
        _text, trusted = build_effective_classification_source("produit", item)
        self.assertFalse(trusted)


if __name__ == "__main__":
    unittest.main()
