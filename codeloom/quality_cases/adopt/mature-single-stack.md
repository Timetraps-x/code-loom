# Mature Single-Stack Adoption

## Repository evidence

A maintained Python/FastAPI service consistently places HTTP translation in `app/api/`, business transitions in `app/services/`, and persistence behind repository interfaces. `pyproject.toml` and CI both run `pytest -q` and Ruff. Representative tests assert service transitions independently of HTTP serialization.

## Expected judgment

- Promote the repository-specific ownership split and its test shape.
- Recommend Python, FastAPI, the maintained module families, and exact verified commands in the project profile.
- Do not emit generic advice such as “write clean code,” “use dependency injection,” or “add tests.”
- Keep commands and profile values outside the constitution candidate.
