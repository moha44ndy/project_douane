"""Étapes de progression affichées pendant une classification Mosam."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

StepStatus = Literal["pending", "active", "done", "skipped"]

CLASSIFICATION_PROGRESS_STEPS: tuple[dict[str, str], ...] = (
    {"id": "merchandise", "label": "Analyse de la marchandise"},
    {"id": "identification", "label": "Identification du produit"},
    {"id": "tec_context", "label": "Recherche du contexte TEC"},
    {"id": "position_hypothesis", "label": "Hypothèse de position (analyse)"},
    {"id": "subposition", "label": "Discrimination TEC (sous-positions)"},
    {"id": "rgi", "label": "Application des RGI"},
    {"id": "duties", "label": "Calcul des droits"},
    {"id": "report", "label": "Génération du rapport"},
)


@dataclass
class ClassificationProgressReporter:
    """Émet des événements SSE sérialisables pendant le pipeline."""

    emit: Callable[[dict[str, Any]], None] | None = None
    statuses: dict[str, StepStatus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for step in CLASSIFICATION_PROGRESS_STEPS:
            self.statuses.setdefault(step["id"], "pending")

    def start(self, step_id: str) -> None:
        self._set(step_id, "active")

    def complete(self, step_id: str) -> None:
        self._set(step_id, "done")

    def skip(self, step_id: str) -> None:
        self._set(step_id, "skipped")

    def complete_all(self) -> None:
        for step in CLASSIFICATION_PROGRESS_STEPS:
            if self.statuses.get(step["id"]) == "pending":
                self.statuses[step["id"]] = "done"
            elif self.statuses.get(step["id"]) == "active":
                self.statuses[step["id"]] = "done"

    def detail(self, message: str) -> None:
        if not self.emit or not message:
            return
        self.emit({"type": "detail", "message": message})

    def _set(self, step_id: str, status: StepStatus) -> None:
        if step_id not in self.statuses:
            return
        self.statuses[step_id] = status
        if not self.emit:
            return
        self.emit(
            {
                "type": "step",
                "step": step_id,
                "status": status,
                "label": next(
                    (s["label"] for s in CLASSIFICATION_PROGRESS_STEPS if s["id"] == step_id),
                    step_id,
                ),
            }
        )


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_init_event() -> str:
    return sse_event({"type": "init", "steps": list(CLASSIFICATION_PROGRESS_STEPS)})
