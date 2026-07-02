import unittest

from sam.classification_analysis import build_structured_classification_analysis
from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index

BACKPACK = """Produit : Sac a dos de randonnee

Composition :
- 45 % polyester
- 30 % cuir bovin
- 20 % nylon
- 5 % aluminium (armature)

Usage :
Transport de materiel de randonnée."""


class TestClassificationAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sample = type(
            "Doc",
            (),
            {
                "page_content": (
                    "4202.92.90.00 --- Autres sacs a dos kg 20 1\n"
                    "Chapitre 42 Notes\n"
                    "3.- A) le n° 42.02 ne comprend pas les sacs en feuilles plastiques."
                )
            },
        )()
        set_tariff_label_index(build_tariff_label_index([sample]))

    def test_why_position_title_uses_retained_code(self) -> None:
        analysis = build_structured_classification_analysis(
            source_text=BACKPACK,
            item={
                "hs_code": "42.02",
                "chapter": "42",
                "description": "Sac a dos de randonnee",
                "justification": "RGI 1 : sac a dos relevant du chapitre 42.",
                "subposition_status": "a_determiner",
                "requires_exterior_surface": True,
            },
            completeness={"requires_exterior_surface": True, "missing_critical": []},
        )
        self.assertEqual(analysis["why_position"]["title"], "Pourquoi 42.02 ?")

    def test_alternatives_parsed_from_justification_not_hardcoded(self) -> None:
        justification = (
            "RGI 1 : sac a dos retenu en 42.02. Chapitre 76 ecarte : l'aluminium est une armature. "
            "Chapitre 63 ecarte : sac fini du chapitre 42."
        )
        analysis = build_structured_classification_analysis(
            source_text=BACKPACK,
            item={
                "hs_code": "42.02",
                "chapter": "42",
                "description": "Sac a dos de randonnee",
                "justification": justification,
            },
            completeness={},
        )
        rejected = [a for a in analysis["alternatives_studied"] if a["status"] == "rejected"]
        self.assertGreaterEqual(len(rejected), 2)
        self.assertNotIn("42.03", [a["code"] for a in rejected if a["code"] == "42.03"])
        codes = " ".join(a["code"] for a in rejected)
        self.assertTrue("76" in codes or "Chapitre 76" in codes)

    def test_no_alternatives_without_justification_detail(self) -> None:
        analysis = build_structured_classification_analysis(
            source_text=BACKPACK,
            item={"hs_code": "42.02", "chapter": "42", "description": "Sac a dos", "justification": ""},
            completeness={},
        )
        self.assertEqual(len(analysis["alternatives_studied"]), 1)
        self.assertEqual(analysis["alternatives_studied"][0]["status"], "retained")

    def test_other_chapter_dynamic_title(self) -> None:
        analysis = build_structured_classification_analysis(
            source_text="Produit : Telephone portable",
            item={
                "hs_code": "8517.13.00.00",
                "chapter": "85",
                "description": "Telephone portable",
                "justification": "RGI 1 : telephone retenu.",
            },
            completeness={},
        )
        self.assertEqual(analysis["why_position"]["title"], "Pourquoi 85.17 ?")


if __name__ == "__main__":
    unittest.main()
