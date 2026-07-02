import json
import unittest
from unittest.mock import patch


from sam import api as api_mod


class TestNormalizeItemKey(unittest.TestCase):
    def test_exact_alias_mapping(self) -> None:
        # Cas: alias exact "pc" -> "ordinateur"
        with patch.object(
            api_mod, "_load_aliases_map", return_value={"pc": "ordinateur", "ordinateur": "ordinateur"}
        ):
            self.assertEqual(api_mod._normalize_item_key("PC"), "ordinateur")

    def test_fuzzy_mapping_singularization_before_fuzzy(self) -> None:
        # Cas: "ordianteurs" doit devenir "ordinateur"
        # (singularisation "ordianteurs" -> "ordianteur", puis fuzzy ordianteur -> ordinateur)
        with patch.object(api_mod, "_load_aliases_map", return_value={"ordinateur": "ordinateur"}):
            self.assertEqual(api_mod._normalize_item_key("ordianteurs"), "ordinateur")

    def test_travaux_exception(self) -> None:
        # "travaux" ne doit pas devenir "traval"
        with patch.object(api_mod, "_load_aliases_map", return_value={}):
            self.assertEqual(api_mod._normalize_item_key("travaux"), "travaux")

    def test_accents_and_punctuation(self) -> None:
        with patch.object(api_mod, "_load_aliases_map", return_value={"telephone": "telephone"}):
            self.assertEqual(api_mod._normalize_item_key("téléphone!"), "telephone")


class TestJsonParsingHelpers(unittest.TestCase):
    def test_extract_classifications_json_direct(self) -> None:
        raw = '{"narrative":"x","classifications":[{"hs_code":"8517.13.00.00","description":"y"}]}'
        cls = api_mod._extract_classifications(raw)
        self.assertEqual(len(cls), 1)
        self.assertEqual(cls[0]["hs_code"], "8517.13.00.00")

    def test_extract_classifications_json_fenced(self) -> None:
        raw = '```json {"narrative":"x","classifications":[{"hs_code":"8471.30.90.00","description":"z"}]} ```'
        cls = api_mod._extract_classifications(raw)
        self.assertEqual(len(cls), 1)
        self.assertEqual(cls[0]["hs_code"], "8471.30.90.00")

    def test_ensure_json_raw_wraps_invalid_json(self) -> None:
        raw = "not-json"
        out = api_mod._ensure_json_raw(raw)
        obj = json.loads(out)
        self.assertIn("error", obj)


class TestSplitMultiArticleEntry(unittest.TestCase):
    def test_comma_in_tariff_description_stays_single_item(self) -> None:
        text = "crème de lait, non concentrés, sans addition de sucre"
        items = api_mod._split_multi_article_entry(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0], text)

    def test_comma_between_distinct_products_splits(self) -> None:
        items = api_mod._split_multi_article_entry("ordinateur, téléphone")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], "ordinateur")
        self.assertEqual(items[1], "téléphone")

    def test_plus_and_et_still_split(self) -> None:
        items = api_mod._split_multi_article_entry("ordinateur + téléphone et clavier")
        self.assertEqual(len(items), 3)

    def test_olive_oil_extra_virgin_single_item(self) -> None:
        text = "huile d'olive, extra vierge"
        items = api_mod._split_multi_article_entry(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0], text)

    def test_composition_block_stays_single_item(self) -> None:
        text = "crème de lait avec composition: non concentrés, reduction de concentré de sucre"
        items = api_mod._split_multi_article_entry(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0], text)

    def test_reduction_clause_after_comma_merges(self) -> None:
        text = "lait, réduction de concentré de sucre"
        items = api_mod._split_multi_article_entry(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0], text)

    def test_two_distinct_products_with_sugar(self) -> None:
        text = "crème de lait non concentrés, sucre avec reduction de concentré"
        items = api_mod._split_multi_article_entry(text)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], "crème de lait non concentrés")
        self.assertEqual(items[1], "sucre avec reduction de concentré")


class TestClassificationResponseNormalization(unittest.TestCase):
    def test_normalize_section_and_chapter_from_hs_code(self) -> None:
        raw = json.dumps(
            {
                "narrative": "x",
                "classifications": [
                    {
                        "hs_code": "8471.30.90.00",
                        "section": "",
                        "chapter": "",
                        "description": "ordinateur",
                    }
                ],
            },
            ensure_ascii=False,
        )
        out = api_mod._normalize_classifications_response(raw)
        obj = json.loads(out)
        cls0 = obj["classifications"][0]
        # 8471 -> chapitre 84 -> section XVI
        self.assertEqual(cls0["chapter"], "84")
        self.assertEqual(cls0["section"], "XVI")


if __name__ == "__main__":
    unittest.main()

