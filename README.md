# Data Profiling Agent (Spark + LLM)

Profiles banking-style tables (Delta/Parquet/CSV or DuckDB-backed tables) using PySpark tools and an optional LLM interpretation step. Outputs a structured `ProfileReport` and persists it as a Delta table.

## Quickstart (Docker)

1. Create `.env` (or export env vars):

```bash
cp .env.example .env
```

2. Generate sample data (optional but recommended):

```bash
python3 scripts/data_gen/ingest_data.py
python3 scripts/init_mock_db.py
```

3. Start services:

```bash
docker compose up --build
```

Then open Streamlit on port `8501` and the API on port `8000`.

## API

`POST /profile` takes a `SourceConfig` and returns a `ProfileReport`.

Example payload (matches the Streamlit UI):

```json
{
  "name": "account",
  "database": "banking",
  "table": "account",
  "connection_type": "duckdb",
  "source_system": "LoanIQ"
}
```

File-based profiling is supported by setting `path` (and optionally `format`):

```json
{
  "name": "account",
  "table": "account",
  "connection_type": "file",
  "path": "data/delta/account",
  "format": "delta",
  "source_system": "LoanIQ"
}
```

## LLM Behavior

If the LLM call fails (missing key, provider error, invalid JSON), the agent returns a best-effort heuristic interpretation so the app still produces a report.

To force offline mode:

```bash
export DISABLE_LLM=true
```

## Data Paths

Most components use `DATA_PATH` as the base directory (defaults to `data/`). In Docker Compose it is set to `/data`.

