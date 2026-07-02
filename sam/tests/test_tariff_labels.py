import json
import unittest

from sam import api as api_mod
from sam.tariff_labels import build_tariff_label_index, lookup_position_label


class TestTariffLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sample_chunks = [
            type(
                "Doc",
                (),
                {
                    "page_content": (
                        "4202.31.00.00 -- A surface exterieure en cuir naturel ou en cuir  \n"
                        "     reconstitue kg 20 1 \n"
                        "8517.13.00.00 -- Telephones intelligents u 10 1"
                    )
                },
            )()
        ]
        cls.index = build_tariff_label_index(sample_chunks)

    def test_build_index_multiline_label(self) -> None:
        label = self.index.get("4202.31.00.00")
        self.assertIsNotNone(label)
        self.assertIn("cuir", label.lower())

    def test_lookup_with_padding(self) -> None:
        label = lookup_position_label("4202.31", self.index)
        self.assertEqual(label, self.index["4202.31.00.00"])

    def test_lookup_exact_code(self) -> None:
        label = lookup_position_label("8517.13.00.00", self.index)
        self.assertIn("Telephones", label)

    def test_normalize_response_enriches_position_label(self) -> None:
        api_mod.set_tariff_label_index(self.index)
        raw = json.dumps(
            {
                "narrative": "x",
                "classifications": [
                    {
                        "hs_code": "4202.31.00.00",
                        "description": "sac a main en cuir",
                    }
                ],
            },
            ensure_ascii=False,
        )
        out = api_mod._normalize_classifications_response(raw)
        obj = json.loads(out)
        self.assertIn("position_label", obj["classifications"][0])
        self.assertIn("cuir", obj["classifications"][0]["position_label"].lower())


if __name__ == "__main__":
    unittest.main()
