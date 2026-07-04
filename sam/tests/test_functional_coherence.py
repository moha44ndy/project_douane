"""Tests du gate de cohérence fonctionnelle (stub — plus de table hardcodée)."""

from __future__ import annotations

import unittest

from sam.functional_coherence import (
    apply_functional_coherence_gate,
    check_functional_coherence,
)


class TestFunctionalCoherence(unittest.TestCase):
    def test_always_returns_none(self) -> None:
        item = {"hs_code": "8517.13.00.00", "confidence": 85}
        prod_id = {"function_usage": "telephone", "product_type": "smartphone"}
        self.assertIsNone(check_functional_coherence(item, prod_id))

    def test_gate_returns_false(self) -> None:
        item = {"hs_code": "9007.11.00.00", "confidence": 88, "justification": "RGI 1"}
        prod_id = {"function_usage": "telephone", "product_type": "smartphone"}
        self.assertFalse(apply_functional_coherence_gate(item, prod_id))

    def test_skipped_identification(self) -> None:
        item = {"hs_code": "9999.00.00.00", "confidence": 90}
        prod_id = {"skipped": True}
        self.assertIsNone(check_functional_coherence(item, prod_id))


if __name__ == "__main__":
    unittest.main()
