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


def branch_slug(branch_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "__", branch_name)
    slug = re.sub(r"__+", "__", slug).strip("_")
    return slug or "detached"


def parse_tasks(content: str) -> list[TaskDefinition]:
    tasks: list[TaskDefinition] = []
    pattern = re.compile(r"^\s*-\s*\[[ xX]\]\s*(T\d+)\s*:\s*(.+?)\s*$")
    for line in content.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        task_id, title = match.groups()
        raw = line.strip()
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        tasks.append(TaskDefinition(task_id=task_id, title=title, raw=raw, fingerprint=fingerprint))
    return tasks
