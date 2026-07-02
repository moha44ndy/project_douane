import unittest

from sam.description_quality import assess_description_quality, is_structured_dossier_text


HANDBAG = """Produit : Sac à main de luxe

Composition :

60 % cuir de crocodile
20 % coton
20 % tissu polyester

Caractéristiques :

Dimensions : 30 × 20 × 10 cm
Doublure en coton
Fermeture métallique
Poignée en cuir de crocodile
Destiné au transport d'effets personnels
provenant de la france et achetée a 22000 dollars
Question

Quel est le code SH ?"""


class TestDescriptionQuality(unittest.TestCase):
    def test_structured_dossier_scores_high(self) -> None:
        self.assertTrue(is_structured_dossier_text(HANDBAG))
        score = assess_description_quality(source_text=HANDBAG)
        self.assertGreaterEqual(score, 85)

    def test_vague_description_scores_low(self) -> None:
        score = assess_description_quality(description="appareil electronique")
        self.assertLess(score, 60)

    def test_rich_llm_description_scores_higher(self) -> None:
        score = assess_description_quality(
            description=(
                "Sac a main de luxe a surface exterieure en cuir naturel de crocodile, "
                "destine au transport d'effets personnels"
            ),
            origin="France",
            value="22000 USD",
            position_label="Sacs a main en cuir",
            justification="RGI 1 : " + ("x" * 80),
        )
        self.assertGreaterEqual(score, 75)


if __name__ == "__main__":
    unittest.main()
