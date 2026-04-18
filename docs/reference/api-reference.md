# API Reference

The Data Profiling Agent provides a RESTful API built with FastAPI. It allows you to trigger profiling jobs, retrieve stored reports, and check the status of the service.

## 🚀 Base URL
The API is typically exposed at `http://localhost:8000`.

---

## 🏥 Health & Status

### `GET /health`
Returns the operational status, agent version, and the currently configured LLM provider.

**Response:**
```json
{
  "status": "online",
  "agent_version": "2.0.0",
  "model": "gemini/gemini-2.5-flash"
}
```

### `GET /`
Simple status check.

---

## 📊 Profiling Endpoints

### `POST /profile`
Triggers a profiling job for a single table.

**Request Body (`SourceConfig`):**
```json
{
  "name": "account_profile",
  "source_system": "Core Banking",
  "table": "accounts",
  "connection_type": "duckdb",
  "database": "banking"
}
```

**Fields:**
- `name` (string): Logical name for the profile.
- `source_system` (string): Origin system (e.g., "LoanIQ", "Mambu").
- `table` (string): Name of the table to profile.
- `connection_type` (enum): One of `duckdb`, `databricks`, `delta`, `parquet`, `csv`, `file`.
- `database` (string, optional): Database name (default: "banking").
- `path` (string, optional): Path to the data file (required if `connection_type` is a file format).
- `format` (enum, optional): `delta`, `parquet`, or `csv`.

**Response:**
Returns a `ProfileReport` object (see [Data Models](../reference/data-models.md)).

### `POST /profile/batch`
Triggers multiple profiling jobs in sequence.

**Request Body:**
A list of `SourceConfig` objects.

**Response:**
A list of `ProfileReport` objects.

---

## 📂 Report Retrieval

### `GET /report/{report_id}`
Retrieves a previously generated profiling report from the Delta Lake storage.

**Parameters:**
- `report_id` (string): The UUID of the report.

**Response:**
A `ProfileReport` object or `404 Not Found`.
