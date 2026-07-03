import json
import unittest

from sam import api as api_mod
from sam.rgi import RgiPipeline, apply_rgi_pipeline_to_response


def _line(hs: str, desc: str, confidence: int = 85) -> dict:
    return {
        "hs_code": hs,
        "description": desc,
        "chapter": hs.split(".")[0][:2] if hs else "",
        "confidence": confidence,
        "justification": "RGI 1 : test.",
    }


class TestRgiPipeline(unittest.TestCase):
    def test_assortiment_coffret_merge_vers_vin(self) -> None:
        source = (
            "Coffret cadeau vendu ensemble comprenant :\n"
            "- 1 bouteille de vin rouge\n"
            "- 2 verres en cristal\n"
            "- 1 tire-bouchon\n"
            "- 1 coffret en bois"
        )
        items = [
            _line("2204.21.00.00", "Bouteille de vin rouge", 92),
            _line("7013.33.00.00", "Verres en cristal", 70),
            _line("8214.10.00.00", "Tire-bouchon", 65),
            _line("4420.90.00.00", "Coffret en bois", 60),
        ]
        result = RgiPipeline().run(source, items)
        self.assertEqual(len(result.classifications), 1)
        self.assertEqual(result.classifications[0]["hs_code"], "2204.21.00.00")
        applied = [r.rule for r in result.applied_rules if r.applied]
        self.assertIn("RGI 3 b", applied)

    def test_sac_composition_rgi1_sans_rgi3b(self) -> None:
        source = (
            "Sac a dos randonnee. Composition : 45% polyester, 30% cuir, 20% nylon, 5% aluminium."
        )
        result = RgiPipeline().run(source, [_line("4202.92.00.00", "Sac a dos", 80)])
        applied = [r.rule for r in result.applied_rules if r.applied]
        self.assertIn("RGI 1", applied)
        not_applied = [r.rule for r in result.not_applied_rules]
        self.assertTrue(any("RGI 3" in r for r in not_applied) or result.stopped_at == "RGI 1")

    def test_plusieurs_produits_demandes_ne_merge_pas(self) -> None:
        items = [
            {**_line("8471.30.90.00", "Ordinateur portable"), "source_query": "Ordinateur portable"},
            {**_line("8517.13.00.00", "Telephone"), "source_query": "telephone smartphone"},
        ]
        data = apply_rgi_pipeline_to_response({"classifications": items})
        self.assertEqual(len(data["classifications"]), 2)

    def test_imprimante_multifonction_decomposee(self) -> None:
        source = "Imprimante multifonction laser avec copieur, scanner et fax"
        items = [
            _line("8443.31.00.00", "Imprimante laser", 90),
            _line("8471.60.00.00", "Scanner", 75),
            _line("8443.31.10.00", "Photocopieur", 72),
        ]
        result = RgiPipeline().run(source, items)
        self.assertEqual(len(result.classifications), 1)
        self.assertIn(result.stopped_at, ("RGI 3 a", "RGI 3 b", "RGI 3 c"))

    def test_normalize_api_pipeline_includes_rgi_engine(self) -> None:
        raw = json.dumps(
            {
                "narrative": "Proposition indicative.",
                "classifications": [
                    {
                        "source_query": "Kit medical d'urgence scelle avec compresses, pansements, gants",
                        "hs_code": "3006.93.00.00",
                        "description": "Trousse medicale",
                        "confidence": 88,
                        "justification": "RGI 1",
                    },
                    {
                        "source_query": "Kit medical d'urgence scelle avec compresses, pansements, gants",
                        "hs_code": "9018.31.00.00",
                        "description": "Seringues",
                        "confidence": 70,
                        "justification": "RGI 1",
                    },
                ],
            },
            ensure_ascii=False,
        )
        out = api_mod._normalize_classifications_response(raw)
        obj = json.loads(out)
        self.assertEqual(len(obj["classifications"]), 1)
        self.assertIn("rgi_engine", obj)
        self.assertIn("rgi_pipeline", obj["classifications"][0])


if __name__ == "__main__":
    unittest.main()
