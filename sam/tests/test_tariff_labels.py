import json
import unittest

from sam import api as api_mod
from sam.tariff_labels import build_tariff_label_index, lookup_position_label, resolve_hs_code_to_tec


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

    def test_resolve_hs_code_replaces_placeholder_subposition(self) -> None:
        from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index

        chunk = type("C", (), {"page_content": (
            "8471.30.10.00 -- Presentes demontes importes pour l'industrie du montage u 5 1\n"
            "8471.30.90.00 -- Autres u 5 1"
        )})()
        set_tariff_label_index(build_tariff_label_index([chunk]))
        rate_index = {
            "8471.30.10.00": {"us_unit": "u", "dd_rate": "5", "rs_rate": "1"},
            "8471.30.90.00": {"us_unit": "u", "dd_rate": "5", "rs_rate": "1"},
        }
        resolved = resolve_hs_code_to_tec(
            "8471.30.00.00",
            description="Ordinateur portable livre monte et neuf",
            rate_index=rate_index,
        )
        self.assertEqual(resolved, "8471.30.90.00")


if __name__ == "__main__":
    unittest.main()
