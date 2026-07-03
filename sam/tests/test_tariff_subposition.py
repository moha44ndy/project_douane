import json
import unittest

from sam.tariff_labels import (
    build_heading_narrative_index,
    build_tariff_label_index,
    resolve_hs_code_to_tec,
    set_heading_narrative_index,
    set_tariff_label_index,
)
from sam.tariff_subposition import apply_subposition_resolution, resolve_subposition_from_tec


class _Chunk:
    def __init__(self, content: str) -> None:
        self.page_content = content


class TestTariffSubposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        chunks = [
            _Chunk(
                "4202.91.10.00 -- Presentes entierement a l'etat demonte ou non monte\n"
                "     importes pour l'industrie du montage kg 20 1\n"
                "4202.91.90.00 -- Autres kg 20 1"
            ),
            _Chunk(
                "84.71 Machines automatiques de traitement de l'information\n"
                "  - Machines automatiques de traitement de l'information\n"
                "     portatives, d'un poids n'excendant pas 10 kg,\n"
                "     comportant au moins une unite centrale de traitement,\n"
                "     un clavier et un ecran :\n"
                "8471.30.10.00 -- Presentes entierement a l'etat demonte ou non monte\n"
                "     importes pour l'industrie du montage u 5 1\n"
                "8471.30.90.00 -- Autres u 5 1\n"
                "  - Autres machines automatiques de traitement de l'information :\n"
                "  -- Comportant, sous une meme enveloppe, au moins une\n"
                "    unite centrale de traitement et, qu'elles soient ou non\n"
                "    combinees, une unite d'entree et une unite de sortie :\n"
                "8471.41.10.00 -- Presentes demontes importes pour l'industrie du montage u 5 1\n"
                "8471.41.90.00 -- Autres u 5 1"
            ),
        ]
        cls.index = build_tariff_label_index(chunks)
        set_tariff_label_index(cls.index)
        set_heading_narrative_index(build_heading_narrative_index(chunks))

    def test_sac_100_cuir_monte_confirme_90(self) -> None:
        source = (
            "Sac de voyage haut de gamme en cuir naturel, destine au transport d'effets personnels, "
            "compose de 100% de cuir, livre monte et neuf, origine italienne"
        )
        result = resolve_subposition_from_tec("4202.91", source)
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.matched_code, "4202.91.90.00")
        self.assertGreaterEqual(result.confidence_cap, 85)
        self.assertEqual(result.final_decision.get("outcome"), "retain_autres")

    def test_sac_mixte_demande_montage_pas_surface(self) -> None:
        source = (
            "Sac de voyage compose de 40% polyester, 35% cuir, 15% aluminium et 10% caoutchouc, "
            "avec doublure polyester"
        )
        result = resolve_subposition_from_tec("4202.91", source)
        self.assertIn(result.status, ("insufficient", "ambiguous"))
        self.assertEqual(result.final_decision.get("outcome"), "stop_insufficient_criteria")
        self.assertTrue(
            any("montage" in m.lower() or "monte" in m.lower() for m in result.missing_criteria),
            result.missing_criteria,
        )
        self.assertFalse(any("surface exterieure" in m.lower() for m in result.missing_criteria))

    def test_sac_mixte_sans_surface_arrete_position(self) -> None:
        source = (
            "Sac de voyage compose de 40% polyester, 35% cuir, 15% aluminium et 10% caoutchouc, "
            "avec doublure polyester"
        )
        result = resolve_subposition_from_tec("4202.91", source)
        self.assertIn(result.status, ("insufficient", "ambiguous"))
        self.assertEqual(result.hs_code, "4202.91")
        self.assertLessEqual(result.confidence_cap, 75)

    def test_apply_updates_item_confidence_cap(self) -> None:
        item = {
            "hs_code": "4202.91",
            "description": "Sac de voyage en cuir",
            "confidence": 90,
            "justification": "RGI 1",
        }
        source = "Sac de voyage 100% cuir livre monte et neuf"
        result = apply_subposition_resolution(item, source_text=source)
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(item["hs_code"], "4202.91.90.00")
        self.assertLessEqual(int(item["confidence"]), 95)

    def test_resolve_invalid_code_uses_subdivision_not_blind_90(self) -> None:
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

    def test_ordinateur_vague_arrete_position_8471(self) -> None:
        result = resolve_subposition_from_tec("8471.30", "ordinateur")
        self.assertEqual(result.status, "insufficient")
        self.assertEqual(result.hs_code, "8471.30")
        self.assertTrue(
            any(
                "montage" in m.lower() or "monte" in m.lower() or "departager" in m.lower()
                for m in result.missing_criteria
            ),
            result.missing_criteria,
        )

    def test_ordinateur_portable_confirme_sous_position(self) -> None:
        source = "Ordinateur portable livre monte et neuf"
        result = resolve_subposition_from_tec("8471.30", source)
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.matched_code, "8471.30.90.00")

    def test_trusted_identification_monte_confirms_code(self) -> None:
        source = (
            "Produit : Sac de voyage\n"
            "Composition :\n- cuir\n"
            "Usage :\nSac de voyage livre monte et neuf"
        )
        item = {
            "hs_code": "4202.91",
            "description": "Sac de voyage",
            "confidence": 90,
            "product_identification": {
                "skipped": False,
                "identification_confidence": 88,
                "enriched_description": source,
                "function_usage": "livre monte et neuf",
            },
        }
        result = apply_subposition_resolution(item, source_text="Sac de voyage")
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.matched_code, "4202.91.90.00")
        self.assertEqual(item.get("classification_status", "confirmee"), "confirmee")

    def test_trusted_identification_surface_departs_only_when_needed(self) -> None:
        discriminant_index = build_tariff_label_index(
            [
                _Chunk(
                    "4202.91.90.00 -- Sacs a dos -- A surface exterieure en cuir naturel kg 20 1\n"
                    "4202.92.90.00 -- Sacs a dos -- A surface exterieure en matieres textiles kg 20 1"
                )
            ]
        )
        set_tariff_label_index(discriminant_index)
        vague = "Sac a dos"
        vague_item = {"hs_code": "4202.91", "description": vague, "confidence": 80}
        vague_result = resolve_subposition_from_tec("4202", vague)
        self.assertTrue(vague_result.missing_criteria)

        enriched = (
            "Produit : Sac a dos\nComposition :\n- tige en cuir\nUsage :\nrandonnee"
        )
        trusted_item = {
            "hs_code": "4202.91",
            "description": vague,
            "confidence": 80,
            "product_identification": {
                "skipped": False,
                "identification_confidence": 90,
                "enriched_description": enriched,
                "materials": ["tige cuir"],
            },
        }
        from sam.classification_source import build_effective_classification_source

        effective, trusted = build_effective_classification_source(vague, trusted_item)
        trusted_result = resolve_subposition_from_tec(
            "4202.91",
            effective,
            trust_identification=trusted,
        )
        self.assertEqual(trusted_result.status, "confirmed")
        self.assertEqual(trusted_result.matched_code, "4202.91.90.00")
        self.assertEqual(trusted_result.final_decision.get("outcome"), "retain_full_code")
        set_tariff_label_index(self.index)


if __name__ == "__main__":
    unittest.main()
