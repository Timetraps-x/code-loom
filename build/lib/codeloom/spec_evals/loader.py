from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from pathlib import Path
from typing import Iterable

from codeloom.spec_evals.models import SpecEvalCase


_BLOCK_PATTERN = re.compile(r"```json\s+spec-eval\s*\n(.*?)\n```", re.DOTALL)
_REQUIRED = (
    "id",
    "title",
    "schema_version",
    "language",
    "entry_request",
    "evidence_packet",
    "review_focus",
    "quality_dimensions",
    "rubric_id",
)


def load_spec_cases(case_dir: Path | None = None) -> tuple[SpecEvalCase, ...]:
    if case_dir is None:
        package = resources.files("codeloom.quality_cases.spec")
        sources = ((item.name, item.read_text(encoding="utf-8"), f"codeloom.quality_cases.spec/{item.name}") for item in package.iterdir() if item.name.endswith(".md") and item.name != "README.md")
    else:
        sources = ((path.name, path.read_text(encoding="utf-8"), str(path)) for path in case_dir.glob("*.md"))
    cases = tuple(_load_case(name, content, source_path) for name, content, source_path in sorted(sources))
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        raise ValueError(f"duplicate spec eval case id: {', '.join(duplicates)}")
    return tuple(sorted(cases, key=lambda case: case.id))


def load_spec_case(case_id: str, case_dir: Path | None = None) -> SpecEvalCase:
    for case in load_spec_cases(case_dir):
        if case.id == case_id:
            return case
    raise ValueError(f"unknown spec eval case: {case_id}")


def _load_case(name: str, content: str, source_path: str) -> SpecEvalCase:
    matches = list(_BLOCK_PATTERN.finditer(content))
    if len(matches) != 1:
        raise ValueError(f"{name}: expected exactly one ```json spec-eval block")
    try:
        metadata = json.loads(matches[0].group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name}: invalid spec-eval JSON: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"{name}: spec-eval metadata must be an object")
    missing = [key for key in _REQUIRED if key not in metadata or metadata[key] in (None, "", [])]
    if missing:
        raise ValueError(f"{name}: missing spec-eval fields: {', '.join(missing)}")
    if metadata["schema_version"] != 1:
        raise ValueError(f"{name}: unsupported spec-eval schema_version: {metadata['schema_version']}")
    text_fields = ("id", "title", "language", "entry_request", "rubric_id")
    invalid_text = [field for field in text_fields if not isinstance(metadata[field], str) or not metadata[field].strip()]
    if invalid_text:
        raise ValueError(f"{name}: spec-eval fields must be non-empty strings: {', '.join(invalid_text)}")
    if Path(name).stem != _slug(str(metadata["id"])):
        raise ValueError(f"{name}: id must match filename stem")
    evidence = _strings(metadata["evidence_packet"], name, "evidence_packet")
    review_focus = _strings(metadata["review_focus"], name, "review_focus")
    dimensions = _strings(metadata.get("quality_dimensions", ()), name, "quality_dimensions")
    narrative = _BLOCK_PATTERN.sub("", content, count=1).strip()
    return SpecEvalCase(
        id=str(metadata["id"]),
        title=str(metadata.get("title") or _title_from_content(content)),
        source_path=source_path,
        source_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        language=str(metadata["language"]),
        entry_request=str(metadata["entry_request"]),
        evidence_packet=evidence,
        review_focus=review_focus,
        quality_dimensions=dimensions,
        rubric_id=str(metadata["rubric_id"]),
        narrative=narrative,
    )


def _strings(value: object, name: str, field: str) -> tuple[str, ...]:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        values = tuple(item for item in value if item.strip())
    else:
        raise ValueError(f"{name}: {field} must be a string list")
    if not values:
        raise ValueError(f"{name}: {field} must not be empty")
    return values


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _title_from_content(content: str) -> str:
    first = next((line.strip()[2:].strip() for line in content.splitlines() if line.startswith("# ")), "Spec eval case")
    return first
