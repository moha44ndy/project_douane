"""
Tests de découpage multi-articles : qualificatifs tarifaires, listes réelles,
formulations ambiguës (virgules, « et », « + », blocs composition).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sam import api as api_mod


def _split(text: str) -> list[str]:
    return api_mod._split_multi_article_entry(text)


class TestSingleProductTariffDescriptions(unittest.TestCase):
    """Une seule marchandise : virgules = qualificatifs TEC/SH."""

    CASES: list[tuple[str, list[str]]] = [
        (
            "crème de lait, non concentrés, sans addition de sucre",
            ["crème de lait, non concentrés, sans addition de sucre"],
        ),
        (
            "Lait et crème de lait, non concentrés ni additionnés de sucre",
            # « et » sépare deux libellés tarifaires proches du TEC (chapitre 04).
            ["Lait", "crème de lait, non concentrés ni additionnés de sucre"],
        ),
        (
            "huile d'olive, extra vierge",
            ["huile d'olive, extra vierge"],
        ),
        (
            "huile de palme, raffinée, désodorisée",
            ["huile de palme, raffinée, désodorisée"],
        ),
        (
            "yoghourt, nature, non additionné de fruits",
            ["yoghourt, nature, non additionné de fruits"],
        ),
        (
            "lait UHT, pasteurisé, homogénéisé",
            ["lait UHT, pasteurisé, homogénéisé"],
        ),
        (
            "beurre, matière grasse 82%",
            ["beurre, matière grasse 82%"],
        ),
        (
            "fromage, affiné en cave",
            ["fromage, affiné en cave"],
        ),
        (
            "riz, long grain, étuvé",
            ["riz, long grain, étuvé"],
        ),
        (
            "lait, réduction de concentré de sucre",
            ["lait, réduction de concentré de sucre"],
        ),
        (
            "ni additionnés de sucre ou d'édulcorants",
            ["ni additionnés de sucre ou d'édulcorants"],
        ),
        (
            "concentré de tomates, en conserve",
            ["concentré de tomates, en conserve"],
        ),
        (
            "produit, même concentré ou additionné de sucre",
            ["produit, même concentré ou additionné de sucre"],
        ),
        (
            "d'une teneur en matières grasses excédant 6 %",
            ["d'une teneur en matières grasses excédant 6 %"],
        ),
    ]

    def test_cases(self) -> None:
        for text, expected in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(_split(text), expected)


class TestCompositionBlocks(unittest.TestCase):
    """Bloc explicite composition:/spécifications: → toujours 1 article."""

    CASES: list[tuple[str, list[str]]] = [
        (
            "crème de lait avec composition: non concentrés, reduction de concentré de sucre",
            [
                "crème de lait avec composition: non concentrés, reduction de concentré de sucre",
            ],
        ),
        (
            "spécifications: teneur en sucre 5%, origine France",
            ["spécifications: teneur en sucre 5%, origine France"],
        ),
        (
            "caractéristiques: non pasteurisé, sans conservateurs",
            ["caractéristiques: non pasteurisé, sans conservateurs"],
        ),
        (
            "composé de: lait entier, ferments lactiques",
            ["composé de: lait entier, ferments lactiques"],
        ),
    ]

    def test_cases(self) -> None:
        for text, expected in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(_split(text), expected)


class TestMultipleDistinctProducts(unittest.TestCase):
    """Virgule ou séparateur fort entre noms de marchandises distincts."""

    CASES: list[tuple[str, list[str]]] = [
        (
            "ordinateur, téléphone",
            ["ordinateur", "téléphone"],
        ),
        (
            "crème de lait non concentrés, sucre avec reduction de concentré",
            ["crème de lait non concentrés", "sucre avec reduction de concentré"],
        ),
        (
            "lait, sucre",
            ["lait", "sucre"],
        ),
        (
            "beurre, fromage",
            ["beurre", "fromage"],
        ),
        (
            "farine, huile, sucre",
            ["farine", "huile", "sucre"],
        ),
        (
            "riz; haricots",
            ["riz", "haricots"],
        ),
        (
            "pc + souris",
            ["pc", "souris"],
        ),
        (
            "téléphone et tablette",
            ["téléphone", "tablette"],
        ),
        (
            "ordinateur + téléphone et clavier",
            ["ordinateur", "téléphone", "clavier"],
        ),
        (
            "bouteille, canette",
            ["bouteille", "canette"],
        ),
        (
            "viande, poisson, volaille",
            ["viande", "poisson", "volaille"],
        ),
    ]

    def test_cases(self) -> None:
        for text, expected in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(_split(text), expected)


class TestAmbiguousAndEdgeCases(unittest.TestCase):
    """Cas limites, accents, casse, entrées courtes ou atypiques."""

    def test_empty_and_whitespace(self) -> None:
        self.assertEqual(_split(""), [])
        self.assertEqual(_split("   "), [])

    def test_single_word_unchanged(self) -> None:
        self.assertEqual(_split("ordinateur"), ["ordinateur"])

    def test_accents_preserved(self) -> None:
        text = "crème de lait, non concentrés"
        self.assertEqual(_split(text), [text])

    def test_uppercase_product_after_comma_splits(self) -> None:
        # Même en majuscule, « Sucre » en tête = nouvel article.
        items = _split("crème de lait, Sucre cristallisé")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1], "Sucre cristallisé")

    def test_sans_addition_then_lait_is_two_segments(self) -> None:
        # Ordre inversé peu naturel : qualificatif seul puis produit.
        items = _split("sans addition de sucre, lait")
        self.assertEqual(items, ["sans addition de sucre", "lait"])

    def test_huile_twice_is_two_products(self) -> None:
        items = _split("huile de palme, huile de coco")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], "huile de palme")
        self.assertEqual(items[1], "huile de coco")

    def test_avec_at_start_of_qualifier_merges(self) -> None:
        text = "produit, avec additifs autorisés"
        self.assertEqual(_split(text), [text])

    def test_contenant_merges(self) -> None:
        text = "préparation, contenant du lactose"
        self.assertEqual(_split(text), [text])

    def test_semicolon_in_tariff_phrase_inside_one_segment(self) -> None:
        # Pas de point-virgule dans la chaîne → 1 article.
        text = "lait, non concentré"
        self.assertEqual(_split(text), [text])


class TestCommaContinuationHelper(unittest.TestCase):
    """Tests unitaires directs sur _is_comma_continuation."""

    def test_reduction_is_continuation(self) -> None:
        self.assertTrue(
            api_mod._is_comma_continuation(
                "réduction de concentré de sucre",
                previous="lait",
            )
        )

    def test_sucre_product_head_is_not_continuation(self) -> None:
        self.assertFalse(
            api_mod._is_comma_continuation(
                "sucre avec réduction de concentré",
                previous="crème de lait non concentrés",
            )
        )

    def test_non_concentre_is_continuation(self) -> None:
        self.assertTrue(
            api_mod._is_comma_continuation(
                "non concentrés",
                previous="crème de lait",
            )
        )

    def test_after_composition_block_merges(self) -> None:
        self.assertTrue(
            api_mod._is_comma_continuation(
                "reduction de concentré de sucre",
                previous="crème avec composition: non concentrés",
            )
        )


class TestExtractItemsPipeline(unittest.TestCase):
    """Chaîne _extract_items_from_txt + _aggregate_items_with_quantities."""

    def test_single_line_tariff_description(self) -> None:
        text = "crème de lait, non concentrés, sans addition de sucre"
        _, items = api_mod._extract_items_from_txt(text, max_items=10)
        unique, counts, _, _ = api_mod._aggregate_items_with_quantities(items, max_items=10)
        self.assertEqual(len(unique), 1)
        self.assertEqual(counts[unique[0]], 1)

    def test_two_products_line(self) -> None:
        text = "crème de lait non concentrés, sucre avec reduction de concentré"
        _, items = api_mod._extract_items_from_txt(text, max_items=10)
        unique, counts, _, _ = api_mod._aggregate_items_with_quantities(items, max_items=10)
        self.assertEqual(len(unique), 2)

    def test_multiline_list(self) -> None:
        text = "ordinateur\n\ntéléphone"
        _, items = api_mod._extract_items_from_txt(text, max_items=10)
        self.assertGreaterEqual(len(items), 2)

    def test_marker_produit_1_produit_2(self) -> None:
        text = "Produit 1: lait\nProduit 2: sucre"
        _, items = api_mod._extract_items_from_txt(text, max_items=10)
        self.assertGreaterEqual(len(items), 2)


class TestStructuredProductDossier(unittest.TestCase):
    """Fiche Produit + Composition + Caractéristiques = 1 seul article."""

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
Question

Quel est le code SH ?"""

    HANDBAG_WITH_ORIGIN_VALUE = """Produit : Sac à main de luxe

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

    def test_table_row_dossier_with_qty_unit_origin_value_stays_single(self) -> None:
        text = """Produit : 6AV2124-0QC02-0A
Quantité :
3 PCE
Origine :
Allemagne
Valeur :
4800 EUR"""
        self.assertTrue(api_mod._is_structured_product_dossier_text(text))
        _, items = api_mod._extract_items_from_txt(text, max_items=50)
        self.assertEqual(len(items), 1)
        unique, counts, _, _ = api_mod._aggregate_items_with_quantities(items, max_items=50)
        self.assertEqual(len(unique), 1)
        self.assertIn("6AV2124", unique[0])
        self.assertIn("Allemagne", unique[0])
        self.assertIn("4800", unique[0])
        self.assertNotIn("PCE", unique[0].splitlines()[0])
        self.assertEqual(counts[unique[0]], 3)
        from sam.rag import split_user_queries

        self.assertEqual(len(split_user_queries(text)), 1)

    def test_noise_unit_and_currency_tokens(self) -> None:
        self.assertTrue(api_mod._is_noise_item_text("PCE"))
        self.assertTrue(api_mod._is_noise_item_text("EUR"))

    def test_dossier_detected_as_single_item(self) -> None:
        _, items = api_mod._extract_items_from_txt(self.HANDBAG, max_items=50)
        self.assertEqual(len(items), 1)
        self.assertIn("Sac à main de luxe", items[0])
        self.assertIn("60 % cuir de crocodile", items[0])
        self.assertNotIn("Quel est le code SH", items[0])

    def test_extract_pipeline_single_item(self) -> None:
        _, items = api_mod._extract_items_from_txt(self.HANDBAG, max_items=50)
        self.assertEqual(len(items), 1)
        unique, _, _, _ = api_mod._aggregate_items_with_quantities(items, max_items=50)
        self.assertEqual(len(unique), 1)

    def test_dossier_with_origin_value_stays_single_item(self) -> None:
        _, items = api_mod._extract_items_from_txt(self.HANDBAG_WITH_ORIGIN_VALUE, max_items=50)
        self.assertEqual(len(items), 1)
        unique, _, _, _ = api_mod._aggregate_items_with_quantities(items, max_items=50)
        self.assertEqual(len(unique), 1)
        self.assertIn("provenant de la france", unique[0].lower())

    def test_commercial_metadata_only_detected(self) -> None:
        self.assertTrue(api_mod._is_commercial_metadata_only_text("achetee a 22000 dollars"))
        self.assertTrue(
            api_mod._is_commercial_metadata_only_text(
                "provenant de la france et achetée a 22000 dollars"
            )
        )

    def test_filter_phantom_classification(self) -> None:
        filtered = api_mod._filter_phantom_classifications(
            [
                {
                    "description": "Sac a main en cuir",
                    "hs_code": "4202.31.00.00",
                },
                {
                    "description": "Article non precise achete a 22000 dollars",
                    "hs_code": "Non renseigne",
                },
            ]
        )
        self.assertEqual(len(filtered), 1)
        self.assertIn("Sac a main", filtered[0]["description"])

    def test_plain_produit_line_without_sections_not_dossier(self) -> None:
        text = "Produit : Ordinateur portable 15 pouces"
        items = _split(text)
        # Pas de section composition → découpage classique (1 bloc).
        self.assertEqual(len(items), 1)


class TestDecimalCommaPreservation(unittest.TestCase):
    """La virgule décimale française ne doit pas couper la description."""

    def test_teneur_with_decimal(self) -> None:
        text = "Lait en poudre, d'une teneur en matières grasses n'excédant pas 1,5 %"
        self.assertEqual(_split(text), [text])

    def test_split_on_commas_helper(self) -> None:
        parts = api_mod._split_on_commas_preserving_decimals("teneur 1,5 %, origine France")
        self.assertEqual(parts, ["teneur 1,5 %", "origine France"])


class TestRealWorldTariffPhrases(unittest.TestCase):
    """Formulations inspirées du libellé TEC CEDEAO (chapitres 04, 17, etc.)."""

    CASES: list[tuple[str, int, str]] = [
        # (texte, nombre d'articles attendu, note courte)
        # « Lait et crème » : le « et » fort sépare (libellé TEC proche mais 2 segments).
        ("0401 Lait et crème de lait, non concentrés, sans addition de sucre", 2, "ch04 et fort"),
        ("crème de lait non concentrés, sucre avec reduction de concentré", 2, "2 marchandises"),
        ("Sucre de canne, brut, sans addition de saccharose", 1, "ch17 qualificatifs"),
        ("Beurre et pâtes à tartiner laitières", 2, "et fort"),
        ("Lait en poudre, d'une teneur en matières grasses n'excédant pas 1,5 %", 1, "teneur décimale"),
        # « Extraits, essences et … » : virgule + « et » → 3 segments (limitation connue).
        ("Extraits, essences et concentrés de café", 3, "et fort + virgule"),
        ("Café, torréfié, non décaféiné", 1, "qualificatifs café"),
        ("Ordinateur portable, téléphone, chargeur", 3, "liste 3 IT"),
    ]

    def test_expected_counts(self) -> None:
        for text, expected_count, note in self.CASES:
            with self.subTest(note=note, text=text):
                items = _split(text)
                self.assertEqual(
                    len(items),
                    expected_count,
                    f"attendu {expected_count}, obtenu {len(items)}: {items}",
                )


class TestStructuredFormDossierSplit(unittest.TestCase):
    """Le tableau structuré ne doit pas être découpé ligne par ligne."""

    def test_bullet_prefixed_dossier_stays_single_query(self) -> None:
        from sam.rag import split_user_queries

        text = """- Produit : rambo magic
Composition :
- liquide
Usage :
pour lutter contre les moustiques
Caractéristiques :
- neuf
Origine :
Nigéria
Valeur :
1000 XOF"""
        queries = split_user_queries(text)
        self.assertEqual(len(queries), 1)
        self.assertIn("rambo magic", queries[0])
        self.assertIn("Composition", queries[0])

    def test_build_structured_inputs_single_item_no_bullet(self) -> None:
        from sam.api import MerchandiseItem, _build_structured_inputs

        items = [
            MerchandiseItem(
                designation="rambo magic",
                material="liquide",
                usage="pour lutter contre les moustiques",
                characteristics="neuf",
                quantity="450",
                unit="ML",
                origin="Nigéria",
                value="1000",
                currency="XOF",
            )
        ]
        classify_input, unique_items, counts, _ = _build_structured_inputs(items)
        self.assertEqual(len(unique_items), 1)
        self.assertFalse(classify_input.startswith("- "))
        self.assertIn("Quantité", classify_input)
        self.assertIn("450 ML", classify_input)
        self.assertEqual(counts[unique_items[0]], 450)

    @patch("sam.product_identification.product_identification_enabled", return_value=True)
    def test_structured_form_skips_identification_when_rich(self, _enabled) -> None:
        from sam.api import (
            MerchandiseItem,
            _build_structured_inputs,
            _should_skip_identification_for_structured,
        )
        from sam.product_identification import prepare_query_for_classification
        from sam.rag import split_user_queries

        items = [
            MerchandiseItem(
                designation="rambo magic",
                material="liquide",
                usage="pour lutter contre les moustiques",
                characteristics="neuf",
                quantity="450",
                unit="ML",
                origin="Nigéria",
                value="1000",
                currency="XOF",
            )
        ]
        self.assertTrue(_should_skip_identification_for_structured(items))
        classify_input, _, _, _ = _build_structured_inputs(items)
        queries = split_user_queries(classify_input)
        self.assertEqual(len(queries), 1)
        _, identification = prepare_query_for_classification(queries[0])
        self.assertTrue(identification.skipped)

    @patch("sam.product_identification.product_identification_enabled", return_value=True)
    def test_structured_form_runs_identification_when_only_designation(self, _enabled) -> None:
        from sam.api import MerchandiseItem, _should_skip_identification_for_structured
        from sam.product_identification import should_run_product_identification

        items = [
            MerchandiseItem(
                designation="iPhone 15",
                material="",
                usage="",
                characteristics="",
                quantity="",
                unit="",
                origin="",
                value="",
                currency="",
            )
        ]
        self.assertFalse(_should_skip_identification_for_structured(items))
        self.assertTrue(should_run_product_identification("iPhone 15"))

    @patch("sam.rag.use_llm", return_value='{"narrative":"","classifications":[]}')
    @patch("sam.rag.retrieve_locked_tec_context", return_value=("", []))
    @patch("sam.rag.prepare_query_for_classification")
    def test_process_user_input_structured_form_never_calls_agent_when_rich(
        self,
        mock_prepare,
        _tec,
        _llm,
    ) -> None:
        from sam.rag import process_user_input

        dossier = (
            "Produit : rambo magic\nComposition :\n- liquide\nUsage :\ninsecticide"
        )
        result = process_user_input(
            dossier,
            chunks=[],
            index=None,
            skip_identification=True,
        )
        mock_prepare.assert_not_called()
        self.assertEqual(len(result.product_identifications), 1)
        self.assertTrue(result.product_identifications[0]["skipped"])
        self.assertEqual(result.product_identifications[0]["skip_reason"], "structured_form")

    @patch("sam.rag.use_llm", return_value='{"narrative":"","classifications":[]}')
    @patch("sam.rag.retrieve_locked_tec_context", return_value=("", []))
    @patch("sam.rag.prepare_query_for_classification")
    def test_process_user_input_sparse_structured_form_calls_agent(
        self,
        mock_prepare,
        _tec,
        _llm,
    ) -> None:
        from sam.product_identification import ProductIdentification
        from sam.rag import process_user_input

        mock_prepare.return_value = (
            "iPhone 15 enrichi",
            ProductIdentification(
                original_query="iPhone 15",
                enriched_description="iPhone 15 enrichi",
                product_name="iPhone 15",
                identification_confidence=85,
            ),
        )
        result = process_user_input(
            "iPhone 15",
            chunks=[],
            index=None,
            skip_identification=False,
        )
        mock_prepare.assert_called_once()
        self.assertFalse(result.product_identifications[0]["skipped"])


if __name__ == "__main__":
    unittest.main()
