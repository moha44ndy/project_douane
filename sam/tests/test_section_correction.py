import json
import unittest

from sam import api as api_mod


class TestSectionCorrectionFromHs(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from sam.tariff_notes import set_chapter_titles_index

        set_chapter_titles_index(
            {
                42: (
                    "Ouvrages en cuir; articles de bourrellerie ou de sellerie; "
                    "articles de voyage, sacs a main et contenants similaires; ouvrages en boyaux"
                )
            }
        )

    def test_chapter_42_gets_section_viii(self) -> None:
        raw = json.dumps(
            {
                "narrative": "x",
                "classifications": [
                    {
                        "hs_code": "4202.92.00.00",
                        "section": "VI",
                        "section_name": "Produits des industries chimiques",
                        "chapter": "42",
                        "description": "Sac a dos",
                        "confidence": 65,
                    }
                ],
            },
            ensure_ascii=False,
        )
        out = api_mod._normalize_classifications_response(raw)
        item = json.loads(out)["classifications"][0]
        self.assertEqual(item["section"], "VIII")
        self.assertIn("pelleteries", item["section_name"].lower())
        self.assertIn("sacs a main", item["section_name"].lower())
        self.assertIn("chapter_name", item)
        self.assertIn("ouvrages en cuir", item["chapter_name"].lower())


if __name__ == "__main__":
    unittest.main()
