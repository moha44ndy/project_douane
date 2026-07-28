import unittest

from sam.structured_tariff_retrieval import StructuredTariffRetriever
from sam.tariff_hierarchy import build_tariff_hierarchy


class TestStructuredTariffRetrieval(unittest.TestCase):
    def setUp(self) -> None:
        hierarchy = build_tariff_hierarchy(
            tariff_labels={
                "8504.40.00.00": "Convertisseurs statiques electriques",
                "8517.13.00.00": "Telephones intelligents",
                "8517.62.00.00": "Appareils pour reception conversion et transmission de donnees",
                "8471.70.00.00": "Unites de memoire pour machines automatiques",
            },
            position_labels={
                "8504": "Transformateurs et convertisseurs electriques statiques",
                "8517": "Appareils de communication et transmission de donnees",
                "8471": "Machines automatiques de traitement de l'information et leurs unites",
            },
        )
        self.retriever = StructuredTariffRetriever(hierarchy)

    def test_indexes_one_document_per_heading(self) -> None:
        self.assertEqual(self.retriever.document_count, 3)

    def test_retrieves_heading_from_descendant_official_labels(self) -> None:
        matches = self.retriever.search("convertisseur statique electrique", top_n=2)
        self.assertEqual(matches[0].position_code, "85.04")
        self.assertIn("convertisseur", matches[0].matched_terms)

    def test_returns_distinct_ranked_headings(self) -> None:
        matches = self.retriever.search("transmission donnees communication", top_n=3)
        self.assertEqual(matches[0].position_code, "85.17")
        self.assertEqual(len({match.position_code for match in matches}), len(matches))

    def test_empty_query_has_no_candidates(self) -> None:
        self.assertEqual(self.retriever.search("de la et pour"), [])


if __name__ == "__main__":
    unittest.main()
