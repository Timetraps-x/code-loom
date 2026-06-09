from __future__ import annotations


def attempt_status(runtime_success: bool, verification_failed: bool) -> str:
    if not runtime_success or verification_failed:
        return "failed"
    return "verified"
