# 📚 API Reference

Technical specifications for the **Data Profiling Agent** API and its underlying data models.

## 📡 Endpoints

### `GET /health`
Returns the status and version of the agent.

### `POST /profile`
Triggers profiling for a single table.

**Request Body:** `SourceConfig`
```json
{
  "name": "Customer Profile",
  "table": "customers",
  "connection_type": "delta",
  "source_system": "CRM"
}
```

**Response:** `ProfileReport`

### `POST /profile/batch`
Triggers profiling for multiple tables.

**Request Body:** `List[SourceConfig]`
**Response:** `List[ProfileReport]`

### `GET /report/{report_id}`
Retrieves a previously generated report.

## 🏗️ Data Models

### `SourceConfig`
Configuration for the source data.
- `name` (Optional): Friendly name for the table.
- `table` (Required): Table name or file path.
- `connection_type` (Required): `delta`, `csv`, or `parquet`.
- `source_system` (Optional): System of origin for metadata context.

### `ProfileReport`
The final output of the profiling agent.
- `report_id`: Unique identifier for the report.
- `source_table`: Name of the profiled table.
- `row_count`: Total rows (or sample count).
- `columns`: List of column schemas (`ColumnSchema`).
- `stats`: Statistical profiles (`ColumnStats`).
- `pii_info`: PII detection results (`PIIProfile`).
- `fk_hints`: Inferred foreign key relationships (`FKHint`).
- `interpretation`: LLM-generated analysis (`LLMInterpretation`).

## 🛠️ Profiling Tools

| Tool | Responsibility |
| --- | --- |
| **SchemaTool** | Infers data types and primary key candidates. |
| **StatsTool** | Calculates distributions, null rates, and detects outliers. |
| **PIITool** | Identifies sensitive data (Email, SSN, Credit Card, etc.) via Spark-native functions. |
| **PatternTool** | Matches regex patterns defined in `config/patterns.yaml`. |
| **RelationTool** | Cross-references tables in the Delta Lake to find join candidates. |

---

[← Back to Main Index](./index.md)
