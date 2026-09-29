# Local AI Benchmark — Local PostgreSQL Setup

## Purpose

This guide creates the two PostgreSQL databases owned by the standalone Local AI
Benchmark Service:

```text
local_ai_benchmark_db
local_ai_benchmark_test
```

Both databases are owned by the Benchmark Service login role:

```text
local_ai_benchmark_app
```

The production/development database stores durable benchmark history. The test
database is reserved for local integration testing and synthetic seed data.

## Important boundary

These databases belong to `local-ai-benchmark`, not `local-ai-router`.

The router does not require PostgreSQL and must not connect directly to these
benchmark persistence tables.

## 1. Create the PostgreSQL role

Open PostgreSQL as the local administrative account:

```bash
sudo -u postgres psql
```

Inside `psql`, create the Benchmark Service login role:

```sql
CREATE ROLE local_ai_benchmark_app WITH LOGIN;
\password local_ai_benchmark_app
```

PostgreSQL will prompt for the password interactively so it does not need to be
stored in shell history or committed to the repository.

If the role already exists, do not recreate it. Change its password instead:

```sql
\password local_ai_benchmark_app
```

## 2. Create the databases

Still inside the administrative `psql` session:

```sql
CREATE DATABASE local_ai_benchmark_db
    OWNER local_ai_benchmark_app;

CREATE DATABASE local_ai_benchmark_test
    OWNER local_ai_benchmark_app;
```

Then leave PostgreSQL:

```text
\q
```

## 3. Export Benchmark Service connection settings

From the repository shell, activate the project virtual environment:

```bash
cd ~/Projects/local-ai-benchmark
source .venv/bin/activate
```

Export the shared connection settings for the current shell:

```bash
export LOCAL_AI_BENCHMARK_DB_HOST="127.0.0.1"
export LOCAL_AI_BENCHMARK_DB_PORT="5432"
export LOCAL_AI_BENCHMARK_DB_USER="local_ai_benchmark_app"
export LOCAL_AI_BENCHMARK_DB_PASSWORD="<your-password>"
```

Do not commit the real password to Git.

## 4. Initialize the durable benchmark database

Point Alembic at the durable Benchmark Service database:

```bash
export LOCAL_AI_BENCHMARK_DB_NAME="local_ai_benchmark_db"
alembic upgrade head
```

Verify the installed revision:

```bash
alembic current
```

## 5. Initialize the local integration-test database

Switch only the database name:

```bash
export LOCAL_AI_BENCHMARK_DB_NAME="local_ai_benchmark_test"
alembic upgrade head
```

Verify it:

```bash
alembic current
```

## 6. Run the full local test suite

Keep `LOCAL_AI_BENCHMARK_DB_NAME` set to `local_ai_benchmark_test` while
running database integration tests:

```bash
ruff check src tests migrations
ruff format --check src tests migrations
python -m pytest -v
```

The PostgreSQL integration test intentionally refuses to run against any
database other than `local_ai_benchmark_test`.

## 7. Switch back to the durable database for normal Benchmark Service work

When running Benchmark Service persistence outside the test suite:

```bash
export LOCAL_AI_BENCHMARK_DB_NAME="local_ai_benchmark_db"
```

The default database name in application configuration is already
`local_ai_benchmark_db`; the explicit export makes the active environment
unambiguous during development.

## Verification queries

To inspect the database directly:

```bash
psql   --host 127.0.0.1   --username local_ai_benchmark_app   --dbname local_ai_benchmark_db
```

Inside `psql`:

```sql
\dn
\dt benchmark.*
SELECT version_num FROM alembic_version;
```

Expected results include the `benchmark` schema, the version-controlled
benchmark tables, and the current Alembic head revision.

## Migration-history rule after initialization

This database setup marks the Benchmark Service migration baseline as
established.

After `local_ai_benchmark_db` has been initialized from this repository
baseline:

- do not rewrite or renumber existing migrations;
- do not edit an applied migration to change schema behavior;
- create a new Alembic revision for every future schema change;
- validate new migration chains in CI against a blank PostgreSQL database.

That keeps persistent benchmark history upgradeable and reproducible.
