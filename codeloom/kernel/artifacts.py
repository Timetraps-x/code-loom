from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    title: str
    raw: str
    fingerprint: str
    lane: str = "build"
    complexity: str = "small"


def branch_slug(branch_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "__", branch_name)
    slug = re.sub(r"__+", "__", slug).strip("_")
    return slug or "detached"


def parse_tasks(content: str) -> list[TaskDefinition]:
    tasks: list[TaskDefinition] = []
    lines = content.splitlines()
    task_pattern = re.compile(r"^\s*-\s*\[[ xX]\]\s*(T\d+)\s*:\s*(.+?)\s*$")
    top_level_section_pattern = re.compile(r"^\s*##\s+")
    current_lane: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        current_lane = _section_lane(line) or current_lane
        match = task_pattern.match(line)
        if not match:
            index += 1
            continue

        task_id, title = match.groups()
        block_end = index + 1
        while (
            block_end < len(lines)
            and not task_pattern.match(lines[block_end])
            and not top_level_section_pattern.match(lines[block_end])
        ):
            block_end += 1

        raw = "\n".join(lines[index:block_end]).strip()
        lane = _block_lane(lines[index + 1 : block_end]) or current_lane or _title_lane(title)
        complexity = _block_complexity(lines[index + 1 : block_end])
        fingerprint = hashlib.sha256(f"{raw}\nLane: {lane}\nComplexity: {complexity}".encode("utf-8")).hexdigest()
        tasks.append(
            TaskDefinition(
                task_id=task_id,
                title=title,
                raw=raw,
                fingerprint=fingerprint,
                lane=lane,
                complexity=complexity,
            )
        )
        index = block_end
    return tasks


def _section_lane(line: str) -> str | None:
    match = re.match(r"^\s*#{2,6}\s*(?:\d+\.\s*)?(build|verify)\b", line, re.IGNORECASE)
    return match.group(1).lower() if match else None


def _block_lane(lines: list[str]) -> str | None:
    pattern = re.compile(r"^\s*-?\s*Lane\s*:\s*(build|verify)\b", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).lower()
    return None


def _block_complexity(lines: list[str]) -> str:
    pattern = re.compile(r"^\s*-?\s*Complexity\s*:\s*(trivial|small|non-trivial)\b", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).lower()
    return "small"


def _title_lane(title: str) -> str:
    normalized = title.strip().lower()
    if normalized.startswith(("verify", "validate", "test", "验证", "测试", "验收", "校验")):
        return "verify"
    return "build"
