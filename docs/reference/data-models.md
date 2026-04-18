# Data Models (Pydantic)

The Data Profiling Agent uses Pydantic v2 models for data validation and serialization. These models are central to the `ProfileReport` produced by the agent.

## `ProfileReport`
The top-level object returned by the profiling agent.

| Field | Type | Description |
| :--- | :--- | :--- |
| `report_id` | `UUID` | Unique identifier for the report. |
| `source_table` | `string` | Name of the profiled table. |
| `source_system` | `string` | Origin system. |
| `profiled_at` | `datetime` | UTC timestamp of the profiling session. |
| `row_count` | `integer` | Total rows in the table. |
| `columns` | `List[ColumnSchema]` | Schema information for each column. |
| `stats` | `List[StatsProfile]` | Statistical profile for each column. |
| `pii_info` | `List[PIIProfile]` | PII detection findings. |
| `fk_hints` | `List[FKHint]` | Potential foreign key relationships discovered. |
| `interpretation` | `LLMInterpretation` | AI-generated summary of the profiling findings. |

---

## `ColumnSchema`
Defines the structure of a single column.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Column name. |
| `spark_type` | `string` | Spark native data type (e.g., `LongType`, `StringType`). |
| `nullable` | `boolean` | Whether the column can contain null values. |
| `is_pk_candidate` | `boolean` | `true` if the column is a potential Primary Key (unique & non-null). |
| `uniqueness_ratio` | `float` | `unique_rows / total_rows` (0.0 to 1.0). |

---

## `StatsProfile`
Contains statistical information for a column.

| Field | Type | Description |
| :--- | :--- | :--- |
| `column` | `string` | Column name. |
| `null_pct` | `float` | Percentage of null values (0.0 to 1.0). |
| `cardinality_est` | `integer` | Approximate count of distinct values (HLL estimate). |
| `min_val` | `Union[int, float, str]` | Minimum value found. |
| `max_val` | `Union[int, float, str]` | Maximum value found. |
| `mean_val` | `float` | Mean value (numeric columns only). |
| `stddev_val` | `float` | Standard deviation (numeric columns only). |
| `has_outliers` | `boolean` | `true` if outliers were detected via the IQR heuristic. |

---

## `PIIProfile`
Represents sensitive data detection findings.

| Field | Type | Description |
| :--- | :--- | :--- |
| `column` | `string` | Column name. |
| `is_pii` | `boolean` | `true` if PII was detected. |
| `pii_type` | `string` | Category (e.g., "EMAIL", "SSN", "IBAN", "NAME"). |
| `confidence` | `float` | Confidence score for the detection. |

---

## `FKHint`
A suggested relationship between two tables.

| Field | Type | Description |
| :--- | :--- | :--- |
| `source_col` | `string` | Column name in the current table. |
| `target_table` | `string` | Name of the suggested related table. |
| `target_col` | `string` | Column name in the target table. |
| `match_ratio` | `float` | Overlap ratio between the two columns. |

---

## `LLMInterpretation`
The AI-generated qualitative summary.

| Field | Type | Description |
| :--- | :--- | :--- |
| `suggested_entity_name` | `string` | Human-friendly name for the table. |
| `bk_candidates` | `List[BKCandidate]` | Potential business keys with reasoning. |
| `pii_summary` | `List[string]` | Human-readable PII findings summary. |
| `dq_flags` | `List[string]` | Specific data quality concerns highlighted by the LLM. |
| `confidence` | `float` | The LLM's self-reported confidence in the interpretation. |
