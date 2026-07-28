import unittest

from sam.tariff_hierarchy import (
    build_tariff_hierarchy,
    format_tariff_code,
    normalize_tariff_code,
    section_for_chapter,
)


class TestTariffHierarchy(unittest.TestCase):
    def setUp(self) -> None:
        self.hierarchy = build_tariff_hierarchy(
            tariff_labels={
                "8471.30.10.00": "Machines automatiques portatives",
                "8471.30.90.00": "Autres",
                "8517.62.00.00": "Appareils pour la transmission de donnees",
            },
            position_labels={
                "8471": "Machines automatiques de traitement de l'information",
                "8517": "Appareils de communication",
            },
            chapter_titles={84: "Machines et appareils mecaniques", 85: "Materiel electrique"},
            tariff_rates={
                "8471.30.10.00": {"us_unit": "u", "dd_rate": "5", "rs_rate": "1"}
            },
        )

    def test_normalize_and_format_supported_levels(self) -> None:
        self.assertEqual(normalize_tariff_code("8471.30.10.00"), "8471301000")
        self.assertEqual(format_tariff_code("84713010"), "8471.30.10")
        self.assertEqual(normalize_tariff_code("847"), "")

    def test_builds_missing_parents_without_inventing_labels(self) -> None:
        hs6 = self.hierarchy.get("8471.30")
        tec8 = self.hierarchy.get("8471.30.10")
        self.assertIsNotNone(hs6)
        self.assertIsNotNone(tec8)
        self.assertTrue(hs6.is_synthetic)
        self.assertEqual(hs6.label, "")
        self.assertEqual(tec8.parent_code, "847130")

    def test_preserves_source_label_rates_and_ancestry(self) -> None:
        line = self.hierarchy.get("8471.30.10.00")
        self.assertEqual(line.label, "Machines automatiques portatives")
        self.assertEqual(line.rates["dd_rate"], "5")
        self.assertIn("Machines automatiques de traitement", line.full_label)
        self.assertEqual(
            [node.level for node in self.hierarchy.ancestors(line.code)],
            ["heading", "hs_subheading", "tec_subheading"],
        )

    def test_parent_child_integrity_and_section_metadata(self) -> None:
        self.assertTrue(self.hierarchy.validation.is_valid)
        self.assertEqual(self.hierarchy.validation.orphan_count, 0)
        self.assertEqual(section_for_chapter(84), "XVI")
        self.assertEqual(self.hierarchy.get("8517").section, "XVI")
        self.assertEqual(
            [node.code for node in self.hierarchy.child_nodes("8471.30.10")],
            ["8471.30.10.00"],
        )

    def test_reports_invalid_source_codes(self) -> None:
        hierarchy = build_tariff_hierarchy(
            tariff_labels={"invalid": "Bad", "8471.30.00.00": "Valid"},
            position_labels={"8471": "Computers"},
        )
        self.assertFalse(hierarchy.validation.is_valid)
        self.assertEqual(hierarchy.validation.invalid_source_codes, ("invalid",))


if __name__ == "__main__":
    unittest.main()
