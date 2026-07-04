"""Vérification de cohérence fonctionnelle (stub).

La cohérence est désormais assurée dynamiquement par :
- La recherche internet (identification produit)
- Le scoring lexical contre l'index TEC (position_validator)
- La discrimination TEC des sous-positions (tariff_subposition)

Aucune table hardcodée.
"""

from __future__ import annotations

from typing import Any


def check_functional_coherence(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return None


def apply_functional_coherence_gate(
    item: dict[str, Any],
    product_identification: dict[str, Any] | None,
) -> bool:
    return False
