# Local AI Benchmark — Testing and CI

## Purpose

The standalone Benchmark Service uses automated quality gates to verify that
benchmark code, persistence, migrations, and service boundaries remain healthy
without depending on the Local AI Router repository.

The CI workflow is defined in:

```text
.github/workflows/ci.yml
```

It runs on pushes and pull requests.

## CI environment

The GitHub Actions job provisions an isolated PostgreSQL 16 service container.

The database is intentionally named:

```text
local_ai_benchmark_test
```

and uses the Benchmark Service-owned test role:

```text
local_ai_benchmark_app
```

This matches the safety guard in the PostgreSQL integration tests. The test
database exists only for the lifetime of the CI job.

No production Benchmark Service credentials are stored in the repository.

## Quality-gate sequence

The workflow performs the following steps:

1. Check out the repository.
2. Install Python 3.12.
3. Install the Benchmark Service and its development dependencies.
4. Run `python -m pip check`.
5. Apply the Alembic migration chain to the disposable PostgreSQL database.
6. Run Ruff lint checks.
7. Verify Ruff formatting.
8. Run the complete pytest suite.

The relevant commands are:

```bash
python -m pip check
alembic upgrade head
ruff check src tests migrations
ruff format --check src tests migrations
python -m pytest -v
```

## PostgreSQL integration testing

The integration-test fixture only executes database tests when
`LOCAL_AI_BENCHMARK_DB_PASSWORD` is present and the configured database is
exactly:

```text
local_ai_benchmark_test
```

CI deliberately supplies those settings so PostgreSQL integration tests execute
rather than being silently skipped.

Alembic initializes the disposable database before pytest runs. This verifies
both the migration chain and the ORM/persistence behavior against a real
PostgreSQL instance.

## Local development

Normal local unit tests can still run without PostgreSQL credentials. Database
integration tests will skip safely when the required test configuration is not
present.

When intentionally running the full database integration suite locally, use the
Benchmark Service test database and environment variables rather than a
development or production database.

## Dependency installation

The repository currently declares dependencies in `pyproject.toml` and does
not yet commit generated lock files.

CI therefore installs:

```bash
python -m pip install -e ".[dev]"
```

Dependency locking can be introduced as a separate reproducibility improvement.
The CI workflow should then be updated to install from those committed lock
files, matching the Local AI Router workflow.

## Boundary principle

Benchmark Service CI must not require:

- the `local-ai-router` repository;
- a running Ollama instance;
- a GPU;
- downloaded local models.

Real model benchmark execution is an explicit operational workflow, not part of
normal deterministic CI.

The deterministic CI suite instead proves that the Benchmark Service itself is
structurally sound and that its PostgreSQL persistence path remains valid.
