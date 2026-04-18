# How-to: Profile a New Table

The Data Profiling Agent is flexible and can profile data from various sources. This guide shows you how to profile your own datasets.

## Option 1: Using the Streamlit UI
This is the easiest way for ad-hoc profiling.
1. Navigate to `http://localhost:8501`.
2. Enter the **Source System** (e.g., "Mambu", "Legacy_DB").
3. Enter the **Database** and **Table Name**.
4. Select the **Connection Type** (e.g., `duckdb`, `databricks`).
5. Click **Run Profiling**.

## Option 2: Using the FastAPI (REST)
For automated workflows or integration into other tools.
Send a `POST` request to `/profile`:

```bash
curl -X POST http://localhost:8000/profile \
     -H "Content-Type: application/json" \
     -d '{
           "name": "customer_profile",
           "source_system": "CRM",
           "table": "customers",
           "connection_type": "file",
           "path": "data/delta/customers",
           "format": "delta"
         }'
```

## Option 3: Profiling Local Files
To profile a CSV or Parquet file on your local machine:
1. Place the file in the `data/` directory.
2. Use the following configuration in your API call or UI:
   - **Connection Type:** `file`
   - **Path:** `data/your_file.csv`
   - **Format:** `csv` (or `parquet`, `delta`)

### 📝 Note on Large Files
If your file is larger than 10 million rows, the agent will automatically take a 1-million-row sample for analysis to ensure the LLM processing remains efficient and within context window limits.

### ⚙️ Custom Spark Options
You can pass custom Spark reader options using the `options` dictionary in the API:
```json
{
  "table": "raw_logs",
  "connection_type": "file",
  "path": "data/logs.csv",
  "format": "csv",
  "options": {
    "header": "true",
    "inferSchema": "true",
    "delimiter": "|"
  }
}
```
