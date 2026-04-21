# API Reference

The **Banking AI Agent Platform** provides a FastAPI interface for programmatic interaction with the profiling agent.

## 🚀 Endpoint: POST /profile

Triggers a profiling run for a single source table.

### 📝 Request Body (`SourceConfig`)

| Field | Type | Description |
| :--- | :--- | :--- |
| **system_name** | `string` | Name of the source system (e.g., "core_banking"). |
| **table_name** | `string` | Name of the table to profile. |
| **path** | `string` | Full file path or Unity Catalog table name. |
| **format** | `string` | Data format (`delta`, `parquet`, `csv`, or `databricks`). |
| **connection_type** | `string` | Connection mode (`local` or `databricks`). |

#### Example: Local Delta Table
```json
{
  "system_name": "faker_banking",
  "table_name": "accounts",
  "path": "/data/delta/accounts",
  "format": "delta",
  "connection_type": "local"
}
```

#### Example: Databricks Table
```json
{
  "system_name": "databricks_prod",
  "table_name": "customers",
  "path": "main.banking.customers",
  "format": "databricks",
  "connection_type": "databricks"
}
```

### ✅ Response (`ProfileReport`)

Returns a comprehensive JSON report containing schema, statistics, patterns, PII, and LLM interpretation.

| Field | Type | Description |
| :--- | :--- | :--- |
| **report_id** | `UUID` | Unique identifier for this profiling run. |
| **timestamp** | `datetime` | When the profiling was performed. |
| **schema** | `dict` | Column types and primary key candidates. |
| **stats** | `dict` | Null rates, cardinality, and outlier info. |
| **llm_interpretation** | `dict` | Business key and entity name suggestions. |

---

## 🚀 Endpoint: GET /report/{id}

Retrieves a previously generated profiling report by its UUID.

### 📝 Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| **id** | `string` | The UUID of the profiling report. |

### ✅ Response

The full `ProfileReport` JSON object or a `404 Not Found` if the report does not exist.

---

[← Back to Main Index](index.md) | [← Return to README](../README.md)
