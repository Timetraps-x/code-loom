from __future__ import annotations

from importlib import resources
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "codeloom"
BUILD_ROOT = ROOT / "build" / "lib" / "codeloom"

QUALITY_CASES = {
    "positive": "python-fastapi.md",
}

LOCAL_ONLY_PACKAGE_PREFIXES = (
    "quality_cases/adopt/",
    "quality_cases/do/",
    "quality_cases/plan/",
    "quality_cases/ship/",
    "quality_cases/spec/",
    "quality_cases/tasks/",
    "spec_evals/",
)


def _managed_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and not path.relative_to(root).as_posix().startswith(LOCAL_ONLY_PACKAGE_PREFIXES)
    }


def test_quality_case_packages_declare_markdown_data():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = configuration["tool"]["setuptools"]["package-data"]

    for package_name in QUALITY_CASES:
        qualified_name = f"codeloom.quality_cases.{package_name}"
        assert (PACKAGE_ROOT / "quality_cases" / package_name / "__init__.py").is_file()
        assert "*.md" in package_data[qualified_name]


def test_packaged_resources_are_readable():
    for package_name, case_name in QUALITY_CASES.items():
        content = resources.files(f"codeloom.quality_cases.{package_name}").joinpath(case_name).read_text(encoding="utf-8")
        assert content.strip()

    assert resources.files("codeloom.templates").joinpath("plan-template.md").read_text(encoding="utf-8").strip()
    assert resources.files("codeloom.roles").joinpath("plan-architect.md").read_text(encoding="utf-8").strip()
    assert not resources.files("codeloom.agents").joinpath("plan-architect.md").is_file()
    assert resources.files("codeloom.projections").joinpath("legacy_claude_code.json").read_text(encoding="utf-8").strip()


def test_build_package_matches_source_package():
    assert BUILD_ROOT.is_dir(), "run `uv build --wheel` before the release test suite"
    assert _managed_files(BUILD_ROOT) == _managed_files(PACKAGE_ROOT)

    for prefix in LOCAL_ONLY_PACKAGE_PREFIXES:
        assert not (BUILD_ROOT / prefix).exists()
