from __future__ import annotations

import hashlib
import json
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
    revision: str = "1"
    depends_on: tuple[str, ...] = ()
    validates: tuple[str, ...] = ()
    covered_by: tuple[str, ...] = ()
    relations_declared: bool = False


@dataclass(frozen=True)
class TaskPacket:
    task_id: str
    title: str
    lane: str
    complexity: str
    revision: str
    task_fingerprint: str
    raw: str
    fields: tuple[tuple[str, tuple[str, ...]], ...]
    depends_on: tuple[str, ...] = ()
    validates: tuple[str, ...] = ()
    covered_by: tuple[str, ...] = ()
    version: str = "2"

    @classmethod
    def from_task(cls, task: TaskDefinition) -> "TaskPacket":
        fields = _task_packet_fields(task.raw)
        return cls(
            task_id=task.task_id,
            title=task.title,
            lane=task.lane,
            complexity=task.complexity,
            revision=task.revision,
            task_fingerprint=task.fingerprint,
            raw=task.raw.replace("\r\n", "\n"),
            fields=tuple((name, tuple(values)) for name, values in sorted(fields.items())),
            depends_on=task.depends_on,
            validates=task.validates,
            covered_by=task.covered_by,
        )

    @classmethod
    def from_canonical_json(cls, content: str) -> "TaskPacket":
        payload = json.loads(content)
        return cls(
            task_id=str(payload["task_id"]),
            title=str(payload["title"]),
            lane=str(payload["lane"]),
            complexity=str(payload["complexity"]),
            revision=str(payload["revision"]),
            task_fingerprint=str(payload["task_fingerprint"]),
            raw=str(payload["raw"]),
            fields=tuple(
                (str(name), tuple(str(value) for value in values))
                for name, values in sorted(dict(payload.get("fields") or {}).items())
            ),
            depends_on=tuple(str(value) for value in payload.get("depends_on") or ()),
            validates=tuple(str(value) for value in payload.get("validates") or ()),
            covered_by=tuple(str(value) for value in payload.get("covered_by") or ()),
            version=str(payload.get("version") or "1"),
        )

    def payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "task_id": self.task_id,
            "title": self.title,
            "lane": self.lane,
            "complexity": self.complexity,
            "revision": self.revision,
            "task_fingerprint": self.task_fingerprint,
            "depends_on": list(self.depends_on),
            "validates": list(self.validates),
            "covered_by": list(self.covered_by),
            "fields": {name: list(values) for name, values in self.fields},
            "raw": self.raw,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

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
        block_lines = lines[index + 1 : block_end]
        lane = _block_lane(block_lines) or current_lane or _title_lane(title)
        complexity = _block_complexity(block_lines)
        revision = _block_revision(block_lines)
        relations = _block_relations(block_lines)
        fingerprint = _task_fingerprint(task_id, title, lane, complexity, revision)
        tasks.append(
            TaskDefinition(
                task_id=task_id,
                title=title,
                raw=raw,
                fingerprint=fingerprint,
                lane=lane,
                complexity=complexity,
                revision=revision,
                depends_on=relations[0],
                validates=relations[1],
                covered_by=relations[2],
                relations_declared=relations[3],
            )
        )
        index = block_end
    return tasks


def task_identity_errors(content: str) -> list[str]:
    errors: list[str] = []
    lines = content.splitlines()
    task_pattern = re.compile(r"^\s*-\s*\[[ xX]\]\s*(T\d+)\s*:\s*(.+?)\s*$")
    top_level_section_pattern = re.compile(r"^\s*##\s+")
    metadata_pattern = re.compile(r"^\s*-?\s*(Lane|Complexity|Revision)\s*:\s*(.*?)\s*$", re.IGNORECASE)
    seen_ids: set[str] = set()
    index = 0

    while index < len(lines):
        match = task_pattern.match(lines[index])
        if not match:
            index += 1
            continue

        task_id = match.group(1)
        if task_id in seen_ids:
            errors.append(f"duplicate_task_id:{task_id}")
        seen_ids.add(task_id)

        block_end = index + 1
        while (
            block_end < len(lines)
            and not task_pattern.match(lines[block_end])
            and not top_level_section_pattern.match(lines[block_end])
        ):
            block_end += 1

        values: dict[str, list[str]] = {}
        for line in lines[index + 1 : block_end]:
            metadata = metadata_pattern.match(line)
            if metadata:
                values.setdefault(metadata.group(1).lower(), []).append(metadata.group(2).strip())

        _validate_task_identity_field(errors, task_id, "lane", values.get("lane", []), {"build", "verify"})
        _validate_task_identity_field(
            errors,
            task_id,
            "complexity",
            values.get("complexity", []),
            {"trivial", "small", "non-trivial"},
        )
        revisions = values.get("revision", [])
        valid_revisions: list[str] = []
        for revision in revisions:
            if not re.fullmatch(r"[^\s]+", revision):
                errors.append(f"invalid_task_revision:{task_id}:{revision or '<empty>'}")
            else:
                valid_revisions.append(revision)
        if len(set(valid_revisions)) > 1:
            errors.append(f"conflicting_task_revision:{task_id}")

        index = block_end

    return errors


def task_relation_errors(content: str) -> list[str]:
    tasks = parse_tasks(content)
    if not tasks or not any(task.relations_declared for task in tasks):
        return []

    errors: list[str] = []
    by_id = {task.task_id: task for task in tasks}
    positions = {task.task_id: index for index, task in enumerate(tasks)}
    for task in tasks:
        fields = _task_packet_fields(task.raw)
        if "depends on" not in fields:
            errors.append(f"missing_task_relation:{task.task_id}:depends_on")
        if task.lane == "build" and "covered by" not in fields:
            errors.append(f"missing_task_relation:{task.task_id}:covered_by")
        if task.lane == "verify" and "validates" not in fields:
            errors.append(f"missing_task_relation:{task.task_id}:validates")

        for field_name, references in (
            ("depends_on", task.depends_on),
            ("validates", task.validates),
            ("covered_by", task.covered_by),
        ):
            raw_values = fields.get(field_name.replace("_", " "), [])
            parsed_values: list[tuple[str, ...]] = []
            for value in raw_values:
                parsed, invalid, duplicates = _parse_task_reference_value(value)
                parsed_values.append(tuple(parsed))
                if invalid:
                    errors.append(f"invalid_task_relation:{task.task_id}:{field_name}:{value or '<empty>'}")
                for reference in duplicates:
                    errors.append(f"duplicate_task_relation:{task.task_id}:{field_name}:{reference}")
            if len(raw_values) > 1:
                errors.append(f"duplicate_task_relation_field:{task.task_id}:{field_name}")
                if len(set(parsed_values)) > 1:
                    errors.append(f"conflicting_task_relation:{task.task_id}:{field_name}")
            elif parsed_values and parsed_values[0] != references:
                errors.append(f"conflicting_task_relation:{task.task_id}:{field_name}")

            for reference in references:
                if reference == task.task_id:
                    errors.append(f"self_task_relation:{task.task_id}:{field_name}")
                    continue
                referenced = by_id.get(reference)
                if referenced is None:
                    errors.append(f"dangling_task_relation:{task.task_id}:{field_name}:{reference}")
                    continue
                if field_name in {"depends_on", "validates"} and positions[reference] >= positions[task.task_id]:
                    errors.append(f"unordered_task_relation:{task.task_id}:{field_name}:{reference}")
                if field_name == "validates" and referenced.lane != "build":
                    errors.append(f"invalid_task_relation_lane:{task.task_id}:validates:{reference}")
                if field_name == "covered_by" and referenced.lane != "verify":
                    errors.append(f"invalid_task_relation_lane:{task.task_id}:covered_by:{reference}")

    for task in tasks:
        for verify_id in task.covered_by:
            verify = by_id.get(verify_id)
            if verify is not None and task.task_id not in verify.validates:
                errors.append(f"task_coverage_mismatch:{task.task_id}:{verify_id}")
        for build_id in task.validates:
            build = by_id.get(build_id)
            if build is not None and task.task_id not in build.covered_by:
                errors.append(f"task_coverage_mismatch:{build_id}:{task.task_id}")

    return list(dict.fromkeys(errors))


def _validate_task_identity_field(
    errors: list[str],
    task_id: str,
    field: str,
    values: list[str],
    allowed: set[str],
) -> None:
    valid_values: list[str] = []
    for value in values:
        normalized = value.lower()
        if normalized not in allowed:
            errors.append(f"invalid_task_{field}:{task_id}:{value or '<empty>'}")
        else:
            valid_values.append(normalized)
    if len(set(valid_values)) > 1:
        errors.append(f"conflicting_task_{field}:{task_id}")



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


def _block_revision(lines: list[str]) -> str:
    pattern = re.compile(r"^\s*-?\s*Revision\s*:\s*([^\s]+)\s*$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return "1"


def _block_relations(lines: list[str]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]:
    fields: dict[str, list[str]] = {}
    pattern = re.compile(r"^\s*-?\s*(Depends on|Validates|Covered by)\s*:\s*(.*?)\s*$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            fields.setdefault(match.group(1).lower(), []).append(match.group(2).strip())

    def references(name: str) -> tuple[str, ...]:
        parsed: list[str] = []
        for value in fields.get(name, []):
            items, _, _ = _parse_task_reference_value(value)
            parsed.extend(items)
        return tuple(dict.fromkeys(parsed))

    return references("depends on"), references("validates"), references("covered by"), bool(fields)


def _parse_task_reference_value(value: str) -> tuple[list[str], bool, list[str]]:
    stripped = value.strip()
    if stripped.lower() == "none":
        return [], False, []
    if not stripped:
        return [], True, []
    parts = [part.strip() for part in stripped.split(",")]
    invalid = any(not re.fullmatch(r"T\d+", part) for part in parts)
    references = [part for part in parts if re.fullmatch(r"T\d+", part)]
    seen: set[str] = set()
    duplicates: list[str] = []
    for reference in references:
        if reference in seen:
            duplicates.append(reference)
        seen.add(reference)
    return references, invalid, duplicates


def _task_packet_fields(raw: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    field_pattern = re.compile(r"^\s*-\s*([A-Za-z][A-Za-z /-]*?)\s*:\s*(.+?)\s*$")
    for line in raw.splitlines()[1:]:
        match = field_pattern.match(line)
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group(1).strip()).lower()
        fields.setdefault(name, []).append(match.group(2).strip())
    return fields


def _task_fingerprint(task_id: str, title: str, lane: str, complexity: str, revision: str) -> str:
    return hashlib.sha256(
        f"{task_id}\n{title.strip()}\nLane: {lane}\nComplexity: {complexity}\nRevision: {revision}".encode("utf-8")
    ).hexdigest()


def _title_lane(title: str) -> str:
    normalized = title.strip().lower()
    if normalized.startswith(("verify", "validate", "test", "验证", "测试", "验收", "校验")):
        return "verify"
    return "build"
