from __future__ import annotations

import unittest

from sam.technical_nature import infer_technical_nature


class TestTechnicalNature(unittest.TestCase):
    def test_infers_industrial_controller_from_observable_capabilities(self) -> None:
        result = infer_technical_nature(
            "Unknown module",
            "Piloter des automatismes et sequences de production",
            "PLC industriel avec entrees sorties",
        )
        self.assertEqual(result.name, "programmable industrial control equipment")
        self.assertGreaterEqual(result.confidence, 70)

    def test_infers_converter_without_brand_or_tariff_code(self) -> None:
        result = infer_technical_nature(
            "Drive unit",
            "Regler la vitesse d'un moteur electrique",
            "Variateur de frequence triphase 400 V",
        )
        self.assertEqual(
            result.name,
            "static electrical power converter or variable speed drive",
        )
        self.assertNotRegex(result.name, r"\d{4}")

    def test_optical_transceiver_wins_over_generic_optical_terms(self) -> None:
        result = infer_technical_nature(
            "Module X",
            "Assurer une liaison optique pour transmettre des donnees",
            "Module optique 100G sur fibre optique",
        )
        self.assertEqual(result.name, "optical data transceiver module")

    def test_infers_accelerator_card_from_pcie_gpu_capabilities(self) -> None:
        result = infer_technical_nature(
            "Compute card",
            "Accelerer le calcul IA dans un serveur",
            "Carte PCIe GPU pour inference et training HPC",
        )
        self.assertEqual(result.name, "data processing accelerator or expansion card")

    def test_infers_mixed_reality_headset_from_display_capabilities(self) -> None:
        result = infer_technical_nature(
            "Wearable display",
            "Afficher des applications immersives",
            "Casque avec affichage spatial micro OLED pour realite mixte",
        )
        self.assertEqual(result.name, "mixed reality display headset")


if __name__ == "__main__":
    unittest.main()
