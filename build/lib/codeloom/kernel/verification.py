from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerificationResult:
    command: str | None
    status: str
    exit_code: int | None
    stdout: str
    stderr: str


class ShellVerifier:
    def run(self, repo_path: Path, commands: dict[str, str]) -> list[VerificationResult]:
        configured = [command for command in commands.values() if command.strip()]
        if not configured:
            return [VerificationResult(None, "skipped_config_missing", None, "", "")]
        results: list[VerificationResult] = []
        for command in configured:
            completed = subprocess.run(
                command,
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
            )
            results.append(
                VerificationResult(
                    command=command,
                    status="passed" if completed.returncode == 0 else "failed",
                    exit_code=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                )
            )
        return results
