from __future__ import annotations

import argparse
import json
from pathlib import Path

from codeloom.spec_evals.executor import FixtureExecutor
from codeloom.spec_evals.loader import load_spec_case, load_spec_cases
from codeloom.spec_evals.runner import run_spec_cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m codeloom.spec_evals")
    parser.add_argument("--case", action="append", dest="case_ids", default=[])
    parser.add_argument("--executor", choices=["fixture", "anthropic"], default="fixture")
    parser.add_argument("--model")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.executor == "anthropic" and not args.live:
        parser.error("--live is required for the anthropic executor")
    if args.executor == "anthropic" and not args.model:
        parser.error("--model is required for the anthropic executor")
    if args.executor == "fixture" and args.live:
        parser.error("--live is only valid with the anthropic executor")

    try:
        cases = [load_spec_case(case_id) for case_id in args.case_ids] if args.case_ids else list(load_spec_cases())
        executor = _executor(args.executor, args.model)
        runs = [run_spec_cases(cases, executor, args.output_dir) for _ in range(args.repeat)]
    except (RuntimeError, ValueError, OSError) as exc:
        print(json.dumps({"status": "execution_error", "error": str(exc)}, ensure_ascii=False))
        return 1

    payload = {
        "status": "ok",
        "runs": [
            {
                "run_id": run.run_id,
                "passed": len(run.passed),
                "failed": len(run.failed),
                "needs_human_review": len(run.needs_human_review),
            }
            for run in runs
        ],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _executor(name: str, model: str | None):
    if name == "fixture":
        return FixtureExecutor()
    from codeloom.spec_evals.anthropic import AnthropicSpecEvalExecutor

    assert model is not None
    return AnthropicSpecEvalExecutor(model)


if __name__ == "__main__":
    raise SystemExit(main())
