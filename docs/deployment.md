# Databricks Deployment Guide

This guide describes how to deploy the **Banking AI Agent Platform** natively to a **Databricks Free Edition** or **Databricks Community Edition** workspace.

## 🚀 Databricks Connectivity

One of the platform's key features is its ability to run identical code in both **Docker** (local dev) and **Databricks** (production). Only three configuration changes are required for this "3-line swap."

### 1. Requirements Switch
When deploying to Databricks, replace `pyspark` with `databricks-connect` in your `requirements.txt`.

```bash
# Instead of requirements.txt
pip install databricks-connect==14.3.1
```

### 2. Configure Environment Variables
Set these variables in your Databricks cluster's **Environment Variables** or via a **Databricks Job** configuration:

| Variable | Value | Description |
| :--- | :--- | :--- |
| **DATABRICKS_HOST** | `https://adb-1234.azuredatabricks.net` | Your workspace URL. |
| **DATABRICKS_TOKEN** | `dapi-secret-token` | A Databricks PAT (Personal Access Token). |
| **DATABRICKS_CATALOG** | `main` | The default Unity Catalog catalog name. |
| **DATABRICKS_SCHEMA** | `banking` | The default Unity Catalog schema name. |
| **GEMINI_API_KEY** | `your-api-key` | Your Google AI Studio API key. |

### 3. Deploy Source Code
You can deploy the agent to Databricks in two ways:
- **Option A: Databricks Repos:** Clone the profiling agent repository directly into your workspace.
- **Option B: Wheel File:** Build a Python wheel (`python setup.py bdist_wheel`) and upload it to a DBFS location or Unity Catalog Volume.

## 🏗️ Connecting to Unity Catalog

The agent uses the **Unity Catalog** for all data operations when running on Databricks.

```python
# Example SourceConfig for Databricks
{
  "system_name": "databricks_prod",
  "table_name": "accounts",
  "path": "main.banking.accounts",
  "format": "databricks",
  "connection_type": "databricks"
}
```

The agent will automatically use the cluster's Spark session to read from Unity Catalog tables without requiring local file paths.

---

[← Back to Main Index](index.md) | [← Return to README](../README.md)
