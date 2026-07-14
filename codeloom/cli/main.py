from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from codeloom import __version__
from codeloom.app.doctor import run_doctor
from codeloom.app.constitution import register_constitution
from codeloom.app.init_project import init_project
from codeloom.app.request import KernelRequest
from codeloom.app.response import KernelResponse
from codeloom.app.stages import StageRunner
from codeloom.app.status import get_status
from codeloom.cli.render import emit_data, emit_kernel_response, render_adopt, render_doctor, render_init, render_status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codeloom")
    parser.add_argument("-v", "--version", action="version", version=f"codeloom {__version__}")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--cwd", default=".")
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--language", choices=["en", "zh"], default="en", help="language for specs deliverable artifacts")
    init_parser.add_argument("--claude-code", action="store_true", help="install Claude Code project skills")
    init_parser.add_argument("--codex", action="store_true", help="select Codex integration when supported")
    init_parser.add_argument("--opencode", action="store_true", help="select OpenCode integration when supported")
    _add_output_flags(init_parser)

    adopt_parser = subparsers.add_parser("adopt")
    adopt_parser.add_argument("--cwd", default=".")
    adopt_parser.add_argument("--constitution", default=".loom/constitution.md")
    _add_output_flags(adopt_parser)

    subparsers.add_parser("kernel")

    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("command", choices=["spec", "plan", "tasks", "do", "ship"])
    stage_parser.add_argument("--cwd", default=".")
    stage_parser.add_argument("--branch", required=True)
    stage_parser.add_argument("--arg", action="append", default=[])
    _add_output_flags(stage_parser)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--cwd", default=".")
    status_parser.add_argument("--branch", required=True)
    _add_output_flags(status_parser)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--cwd", default=".")
    _add_output_flags(doctor_parser)

    args = parser.parse_args(argv)
    if args.subcommand == "init":
        integrations = _parse_init_integrations(args)
        created, path = init_project(Path(args.cwd), force=args.force, integrations=integrations, language=args.language)
        payload = {
            "status": "ok",
            "message": "project initialized" if created else "project already initialized",
            "created": created,
            "project_path": path,
            "integrations": sorted(integrations),
            "language": args.language,
        }
        emit_data(payload, args.json_output, render_init)
        return 0
    if args.subcommand == "adopt":
        try:
            payload = register_constitution(Path(args.cwd), args.constitution)
        except ValueError as exc:
            payload = {"status": "failed", "message": str(exc), "constitution": {}, "errors": [str(exc)]}
        emit_data(payload, args.json_output, render_adopt)
        return 0 if payload["status"] == "ok" else 1
    if args.subcommand == "kernel":
        return _run_kernel_stdin()
    if args.subcommand == "stage":
        response = _run_stage(args.cwd, args.branch, args.command, _parse_args(args.arg))
        emit_kernel_response(response, args.json_output)
        return 0 if response.status in {"ok", "noop"} else 1
    if args.subcommand == "status":
        payload = get_status(Path(args.cwd), args.branch)
        emit_data(payload, args.json_output, render_status)
        return 0 if payload["status"] != "failed" else 1
    if args.subcommand == "doctor":
        payload = run_doctor(Path(args.cwd))
        emit_data(payload, args.json_output, render_doctor)
        return 0 if payload["status"] != "failed" else 1
    return 1


def _run_stage(cwd: str, branch: str, command: str, args: dict[str, str]) -> KernelResponse:
    request = KernelRequest(
        cwd=Path(cwd).resolve(),
        branch_name=branch,
        command=command,
        args=args,
    )
    return StageRunner().run(request)


def _run_kernel_stdin() -> int:
    try:
        data = json.loads(sys.stdin.read())
        request = KernelRequest.from_dict(data)
        response = StageRunner().run(request)
    except Exception as exc:
        response = KernelResponse(status="failed", message=str(exc), errors=[type(exc).__name__])
    print(json.dumps(response.to_dict(), ensure_ascii=False, separators=(",", ":")))
    return 0 if response.status in {"ok", "noop"} else 1


def _add_output_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", dest="json_output", action="store_true", help="emit compact JSON for machine consumers")
    group.add_argument("--human", dest="json_output", action="store_false", help="emit concise human-readable output")
    parser.set_defaults(json_output=False)


def _parse_init_integrations(args: argparse.Namespace) -> set[str]:
    integrations = set()
    if args.claude_code:
        integrations.add("claude-code")
    if args.codex:
        integrations.add("codex")
    if args.opencode:
        integrations.add("opencode")
    return integrations or {"claude-code"}
def _parse_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            parsed[value] = ""
            continue
        key, item = value.split("=", 1)
        parsed[key] = item
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
