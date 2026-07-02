import unittest

from sam.tariff_position_rules import (
    build_surface_sensitive_positions,
    is_subposition_sensitive_position,
    position_code_from_hs,
    set_surface_sensitive_positions,
)


class TestTariffPositionRules(unittest.TestCase):
    def test_build_surface_sensitive_from_labels(self) -> None:
        index = {
            "4202.92.90.00": "Sacs a dos -- A surface exterieure en cuir",
            "7616.99.90.00": "Autres ouvrages en aluminium",
        }
        positions = build_surface_sensitive_positions(index)
        self.assertIn("42.02", positions)
        self.assertNotIn("76.16", positions)

    def test_is_subposition_sensitive_after_index(self) -> None:
        set_surface_sensitive_positions({"42.02"})
        self.assertTrue(is_subposition_sensitive_position("4202.22.90.00"))
        self.assertFalse(is_subposition_sensitive_position("7616.99.90.00"))

    def test_position_code_from_hs(self) -> None:
        self.assertEqual(position_code_from_hs("4202.22.90.00"), "42.02")
        self.assertEqual(position_code_from_hs("42.02"), "42.02")


if __name__ == "__main__":
    unittest.main()
