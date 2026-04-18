# Explanation: Databricks Deployment

**[Home](../index.md) / [Architecture](../index.md#🏗️-architecture--concepts) / Databricks Deployment**

The Data Profiling Agent is designed to be **platform-agnostic**, allowing for seamless transitions between local development (Docker) and enterprise deployment (Databricks).

## 🌍 The Deployment Strategy

We maintain identical agent logic across all environments. The only difference is in the **Spark Session Factory** and the **Target Storage Path**.

### 1. Swapping the Spark Engine

To use Databricks as the compute engine, we replace `pyspark` with `databricks-connect` in our requirements.

| Local (Docker) | Databricks |
| :--- | :--- |
| Uses local `pyspark` (bundled) | Uses `databricks-connect` (remote) |
| Connects to local Spark Master | Connects to Databricks SQL Warehouse |

### 2. Connection Configuration

Update your `.env` file with your Databricks credentials:

```env
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi_your_token
DATABRICKS_CATALOG=main
DATABRICKS_SCHEMA=banking
```

### 3. Unity Catalog Integration

When running in Databricks mode, the `DeltaWriter` can write directly to **Unity Catalog (UC)** managed tables. This provides several enterprise benefits:
*   **Centralized Governance:** All `ProfileReports` are visible and governed by UC permissions.
*   **Lineage:** Databricks tracks lineage between your source banking tables and the generated profiles.
*   **Auditability:** Built-in audit logs in Databricks complement the agent's immutable report storage.

## 🚀 How to Switch (Code-wise)

The `src/reader/spark_session.py` factory is designed to detect your environment:

```python
if os.getenv("DATABRICKS_HOST"):
    # Initialize Databricks Connect session
    # Uses cluster ID or SQL Warehouse ID
else:
    # Initialize Local Spark Session
```

---
[**❮ Previous: Spark Tooling Deep Dive**](spark-tools.md) | [**Next: API Reference ➔**](../reference/api-reference.md)
