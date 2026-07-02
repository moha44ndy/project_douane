import json
import unittest
from pathlib import Path

from sam import api as api_mod
from sam.classification_completeness import build_provisional_ch42_narrative
from sam.tariff_rates import (
    OTHER_TAXES_OUT_OF_TEC,
    PROVISIONAL_TAX_VALUE,
    PROVISIONAL_US_VALUE,
    build_tariff_rate_index,
    enrich_item_tariff_rates,
    lookup_tariff_rates,
    set_tariff_rate_index,
)


class _Chunk:
    def __init__(self, content: str) -> None:
        self.page_content = content


def _load_chunks_sample() -> list[_Chunk]:
    chunks_path = Path(__file__).resolve().parents[1] / "chunks.json"
    with chunks_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return [_Chunk(item if isinstance(item, str) else str(item)) for item in data]


class TestTariffRates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = build_tariff_rate_index(_load_chunks_sample())
        set_tariff_rate_index(cls.index)

    def test_backpack_code_has_kg_20_1(self) -> None:
        rates = lookup_tariff_rates("4202.92.90.00", self.index)
        self.assertIsNotNone(rates)
        assert rates is not None
        self.assertEqual(rates["us_unit"], "kg")
        self.assertEqual(rates["dd_rate"], "20")
        self.assertEqual(rates["rs_rate"], "1")

    def test_provisional_position_does_not_show_certain_rates(self) -> None:
        item = {
            "hs_code": "42.02",
            "chapter": "42",
            "description": "Sac a dos de randonnee",
            "product_name": "Sac a dos de randonnee",
            "subposition_status": "a_determiner",
            "classification_status": "provisoire",
        }
        enrich_item_tariff_rates(item, self.index)
        self.assertEqual(item["dd_rate"], PROVISIONAL_TAX_VALUE)
        self.assertEqual(item["rs_rate"], PROVISIONAL_TAX_VALUE)
        self.assertEqual(item["us_unit"], PROVISIONAL_US_VALUE)
        self.assertEqual(item["other_taxes"], OTHER_TAXES_OUT_OF_TEC)
        self.assertEqual(item["taxes_source"], "provisional")

    def test_confirmed_subposition_uses_tec_rates(self) -> None:
        item = {
            "hs_code": "4202.92.90.00",
            "chapter": "42",
            "classification_status": "confirmee",
        }
        enrich_item_tariff_rates(item, self.index)
        self.assertEqual(item["dd_rate"], "20 %")
        self.assertEqual(item["rs_rate"], "1 %")
        self.assertEqual(item["us_unit"], "KG")
        self.assertEqual(item["taxes_source"], "tec")

    def test_normalize_provisional_backpack_uses_placeholders(self) -> None:
        set_tariff_rate_index(self.index)
        raw = json.dumps(
            {
                "narrative": "x",
                "classifications": [
                    {
                        "hs_code": "4202.92.00.00",
                        "chapter": "42",
                        "description": "Sac a dos de randonnee",
                        "confidence": 65,
                        "dd_rate": "5 %",
                        "rs_rate": "2 %",
                        "us_unit": "PIECE",
                        "other_taxes": "TVA 18 %",
                        "source_query": (
                            "Produit : Sac a dos de randonnee\n\n"
                            "Composition :\n- 45 % polyester\n- 30 % cuir bovin\n"
                        ),
                    }
                ],
            },
            ensure_ascii=False,
        )
        out = api_mod._normalize_classifications_response(raw)
        item = json.loads(out)["classifications"][0]
        self.assertEqual(item["dd_rate"], PROVISIONAL_TAX_VALUE)
        self.assertEqual(item["us_unit"], PROVISIONAL_US_VALUE)
        self.assertEqual(item["taxes_source"], "provisional")

    def test_provisional_narrative_structure(self) -> None:
        narrative = build_provisional_ch42_narrative(
            [
                {
                    "requires_exterior_surface": True,
                    "product_name": "Sac a dos de randonnee",
                }
            ]
        )
        self.assertIn("Produit analyse\nSac a dos de randonnee", narrative)
        self.assertNotIn("Pour Sac a dos", narrative)


if __name__ == "__main__":
    unittest.main()
