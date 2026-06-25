from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KernelResponse:
    status: str
    message: str
    recommended_next: str | None = None
    recommended_task_id: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "recommended_next": self.recommended_next,
            "recommended_task_id": self.recommended_task_id,
            "artifact_paths": self.artifact_paths,
            "findings": self.findings,
            "errors": self.errors,
            "extras": self.extras,
        }
