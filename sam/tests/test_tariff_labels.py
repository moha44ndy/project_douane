import json
import unittest

from sam import api as api_mod
from sam.tariff_labels import (
    build_position_label_index,
    build_tariff_label_index,
    find_positions_by_label_keywords,
    lookup_position_label,
    resolve_hs_code_to_tec,
    set_heading_narrative_index,
)


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

    def test_position_heading_on_same_line_as_full_code_is_indexed(self) -> None:
        chunk = type("C", (), {"page_content": (
            "96.17 9617.00.00.00 Bouteilles isolantes et autres recipients isothermiques\n"
            "montes, dont l'isolation est assuree par le vide, ainsi que leurs parties. kg 20 1\n"
            "96.18 9618.00.00.00 Mannequins et articles similaires. kg 20 1"
        )})()
        position_index = build_position_label_index({}, chunks=[chunk])
        self.assertIn("9617", position_index)
        self.assertIn("isothermiques", position_index["9617"])
        self.assertNotIn("Mannequins", position_index["9617"])

    def test_keyword_search_can_use_heading_narratives_for_tablet_family(self) -> None:
        api_mod.set_tariff_label_index(
            {
                "8471.30.10.00": "Presentes demontes importes pour l'industrie du montage",
                "8471.30.90.00": "Autres",
            }
        )
        set_heading_narrative_index(
            {
                "8471.30": (
                    "machines automatiques de traitement de l information portatives "
                    "comportant au moins une unite centrale de traitement un clavier et un ecran"
                )
            }
        )

        matches = find_positions_by_label_keywords(
            ["machines", "automatiques", "traitement", "information", "portatives", "unites"],
            min_matches=2,
            top_n=5,
        )

        self.assertTrue(any(position == "84.71" for position, _, _ in matches))


if __name__ == "__main__":
    unittest.main()
