from __future__ import annotations

import csv
import unittest
from pathlib import Path

from sam.functional_profile import build_functional_profile


class TestClientRegressionTechnicalNature(unittest.TestCase):
    def test_all_client_rows_derive_generic_technical_nature_without_api(self) -> None:
        expected = {
            "Cisco Catalyst 9300": "network data switching or routing equipment",
            "Huawei OceanStor Dorado": "complete data storage system or storage unit",
            "DJI Zenmuse H30T": "digital video or thermal imaging camera",
            "iPad Pro M4": "portable tablet or hybrid data processing computer",
            "KUKA KR 16 R1610": "industrial robot",
            "Omron NX102-1200": "programmable industrial control equipment",
            "ABB ACS880-01-430A-3": "static electrical power converter or variable speed drive",
        }
        with Path("sample_client_regression_7.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 7)
        for row in rows:
            designation = row["designation"]
            source = (
                f"Produit : {designation}\n"
                f"Composition : {row['matiere / composition']}\n"
                f"Usage : {row['usage']}\n"
                f"Caracteristiques : {row['caracteristiques']}"
            )
            profile = build_functional_profile(source, {"skipped": True})
            with self.subTest(designation=designation):
                self.assertEqual(profile.product_type, expected[designation])
                self.assertNotEqual(profile.product_type, designation)
                self.assertGreaterEqual(profile.technical_nature_confidence, 70)


if __name__ == "__main__":
    unittest.main()
