from __future__ import annotations


def attempt_status(task_lane: str, runtime_success: bool, verification_failed: bool) -> str:
    if not runtime_success or verification_failed:
        return "failed"
    if task_lane == "verify":
        return "verified"
    return "implemented"
