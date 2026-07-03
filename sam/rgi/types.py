from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RgiRuleRecord:
    rule: str
    applied: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "applied": self.applied, "reason": self.reason}


@dataclass
class RgiPipelineResult:
    source_text: str
    classifications: list[dict[str, Any]] = field(default_factory=list)
    applied_rules: list[RgiRuleRecord] = field(default_factory=list)
    not_applied_rules: list[RgiRuleRecord] = field(default_factory=list)
    positions_studied: list[str] = field(default_factory=list)
    positions_rejected: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    confidence_cap: int | None = None
    stopped_at: str = ""
    essential_character: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_text": self.source_text[:200],
            "applied_rules": [r.to_dict() for r in self.applied_rules],
            "not_applied_rules": [r.to_dict() for r in self.not_applied_rules],
            "positions_studied": self.positions_studied,
            "positions_rejected": self.positions_rejected,
            "missing_information": self.missing_information,
            "confidence_cap": self.confidence_cap,
            "stopped_at": self.stopped_at,
            "essential_character": self.essential_character,
        }
