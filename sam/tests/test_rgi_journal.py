import unittest

from sam.rgi.journal import attach_rgi_journal_to_item, build_rgi_technical_journal, format_rgi_journal_text
from sam.rgi import RgiPipeline


def _line(hs: str, desc: str, confidence: int = 85) -> dict:
    return {
        "hs_code": hs,
        "description": desc,
        "chapter": hs.split(".")[0][:2] if hs else "",
        "confidence": confidence,
        "justification": "RGI 1 : hypothese LLM ignoree en aval.",
    }


class TestRgiJournal(unittest.TestCase):
    def test_sac_simple_journal_rgi1_et_rgi6(self) -> None:
        source = (
            "Sac de voyage haut de gamme en cuir, compose de 100% de cuir, "
            "livre monte et neuf"
        )
        pipeline_result = RgiPipeline().run(source, [_line("4202.91.90.00", "Sac de voyage", 80)])
        item = dict(pipeline_result.classifications[0])
        item["subposition_status"] = "a_determiner"
        item["subposition_resolution"] = {
            "status": "insufficient",
            "hs_code": "4202.91",
            "missing_criteria": ["Etat de presentation : monte ou demonte/non monte"],
        }

        journal = attach_rgi_journal_to_item(item)
        text = format_rgi_journal_text(journal)

        self.assertIn("RGI appliquees", text)
        self.assertIn("+ RGI 1", text)
        self.assertIn("+ RGI 6", text)
        self.assertNotIn("non evaluee", text.lower())
        self.assertNotIn("RGI 3 b", item["justification"])

    def test_journal_ne_depend_pas_du_texte_llm(self) -> None:
        item = {
            "hs_code": "4202.91",
            "description": "Sac de voyage",
            "justification": "RGI 3 b : le cuir predomine. RGI 4 appliquee par erreur.",
            "rgi_pipeline": {
                "stopped_at": "RGI 1",
                "applied_rules": [
                    {"rule": "RGI 1", "applied": True, "reason": "Position retenue selon libelle TEC."}
                ],
                "not_applied_rules": [
                    {"rule": "RGI 2 a", "applied": False, "reason": "Produit fini ou monte."},
                    {"rule": "RGI 2 b", "applied": False, "reason": "Pas de melange declenchant conflit."},
                    {"rule": "RGI 3", "applied": False, "reason": "Une seule position candidate apres RGI 1."},
                    {"rule": "RGI 4", "applied": False, "reason": "Analogie non necessaire."},
                    {"rule": "RGI 5", "applied": False, "reason": "Emballages integres : pas de ligne separee."},
                ],
            },
            "subposition_status": "a_determiner",
            "subposition_resolution": {"status": "insufficient", "hs_code": "4202.91"},
        }
        journal = build_rgi_technical_journal(item)
        applied = journal.get("applied_rules") or []
        self.assertIn("RGI 1", applied)
        self.assertIn("RGI 6", applied)
        self.assertNotIn("RGI 3 b", applied)
        self.assertNotIn("RGI 4", applied)

        rgi3 = next(e for e in journal["entries"] if e["rule"] == "RGI 3")
        self.assertEqual(rgi3["status"], "not_applicable")

    def test_decision_engine_inclut_journal_dans_justification(self) -> None:
        from sam.decision_engine import render_outputs_from_decision

        item = {
            "hs_code": "4202.91",
            "chapter": "42",
            "classification_status": "provisoire",
            "subposition_status": "a_determiner",
            "confidence": 75,
            "justification": "RGI 3 b invente par le modele.",
            "rgi_pipeline": {
                "stopped_at": "RGI 1",
                "applied_rules": [
                    {"rule": "RGI 1", "applied": True, "reason": "Position retenue."}
                ],
                "not_applied_rules": [
                    {"rule": "RGI 2 a", "applied": False, "reason": "Non concernee."},
                    {"rule": "RGI 2 b", "applied": False, "reason": "Produit non composite."},
                    {"rule": "RGI 3", "applied": False, "reason": "Une seule position possible."},
                    {"rule": "RGI 4", "applied": False, "reason": "Analogie non necessaire."},
                    {"rule": "RGI 5", "applied": False, "reason": "Non concernee."},
                ],
            },
            "subposition_resolution": {
                "status": "insufficient",
                "hs_code": "4202.91",
                "missing_criteria": ["Critere TEC manquant"],
            },
            "missing_fields": ["Critere TEC manquant"],
        }
        source = "Sac de voyage 100% cuir"
        render_outputs_from_decision(item, source)
        self.assertIn("rgi_journal", item)
        self.assertIn("RGI appliquees", item["justification"])
        self.assertNotIn("RGI 3 b invente", item["justification"])
        self.assertIn("[TEC]", item["justification"])

    def test_narrative_does_not_duplicate_rgi_journal(self) -> None:
        from sam.decision_engine import build_narrative_from_classifications
        from sam.rgi.journal import attach_rgi_journal_to_item

        item = {
            "hs_code": "8528.52.00.00",
            "chapter": "85",
            "description": "6AV2124-0QC02-0AX",
            "source_query": "Produit : 6AV2124-0QC02-0AX",
            "classification_status": "confirmee",
            "confidence": 95,
            "subposition_resolution": {
                "status": "confirmed",
                "matched_code": "8528.52.00.00",
                "explanation": "Une seule sous-position confirmee.",
            },
            "rgi_pipeline": {
                "stopped_at": "RGI 6",
                "applied_rules": [
                    {"rule": "RGI 1", "applied": True, "reason": "Position retenue."},
                    {"rule": "RGI 6", "applied": True, "reason": "Sous-position confirmee."},
                ],
            },
        }
        attach_rgi_journal_to_item(item)
        narrative = build_narrative_from_classifications([item])
        self.assertEqual(narrative.count("RGI appliquees"), 1)
        self.assertNotIn("RGI appliquees |  | +", narrative)


if __name__ == "__main__":
    unittest.main()
