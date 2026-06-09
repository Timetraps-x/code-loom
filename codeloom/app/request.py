from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KernelRequest:
    cwd: Path
    branch_name: str
    command: str
    args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KernelRequest":
        cwd = data.get("cwd")
        branch_name = data.get("branch_name")
        command = data.get("command")
        if not cwd:
            raise ValueError("KernelRequest.cwd is required")
        if not branch_name:
            raise ValueError("KernelRequest.branch_name is required")
        if not command:
            raise ValueError("KernelRequest.command is required")
        return cls(
            cwd=Path(str(cwd)).resolve(),
            branch_name=str(branch_name),
            command=str(command),
            args=dict(data.get("args") or {}),
        )
