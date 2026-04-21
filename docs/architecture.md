# Architecture Deep-Dive

The **Banking AI Agent Platform** utilizes a sophisticated agentic architecture to automate data profiling. This document explains the internal reasoning and data flow within **Agent 1: The Data Profiling Agent**.

## 🧬 Agentic Workflow (LangGraph)

The profiling agent is implemented as a **deterministic DAG** (Directed Acyclic Graph) using **LangGraph**. Unlike a standard ReAct agent, it follows a structured process to ensure consistent results across different tables.

### 1. Reader Node (`node_reader`)
The entry point of the graph. It uses **PySpark** to load data from multiple formats (Delta, Parquet, CSV, or Databricks table).
- **Sampling Guard:** If a table exceeds 10 million rows, it automatically samples to 1 million to maintain tool performance while reporting the full row count.
- **Connection Logic:** Supports both local file paths and remote Databricks Unity Catalog connections.

### 2. Profiler Node (`node_profiler`)
A "God Node" that executes five specialized tools sequentially:
- **Schema Tool:** Extracted column types, primary key candidates, and HLL-based unique counts.
- **Stats Tool:** Single-pass aggregations for null rates, cardinality, and IQR-based outliers.
- **Pattern Tool:** Config-driven regex matching for universal banking formats (IBAN, SWIFT) and source-specific IDs.
- **PII Tool:** Heuristic detection for sensitive data (Emails, SSNs, Names).
- **Relation Tool:** Distinct-join-based containment scoring to suggest foreign key hints.

### 3. Summarizer Node (`node_summarizer`)
Compresses raw tool outputs into a dense JSON payload suitable for the LLM's context window. It filters for "high-interest" columns like those with PII, high null rates, or strong PK candidates.

### 4. Interpreter Node (`node_interpreter`)
The **LLM (Gemini 2.5 Flash)** analyzes the summarized tool outputs to make semantic judgments:
- **Business Key Inference:** "Based on pattern X and uniqueness Y, Column Z is a Business Key candidate."
- **Confidence Scoring:** Assigns a 0.0 to 1.0 confidence score to every judgment.
- **Entity Identification:** Suggests the business entity name (e.g., "Customer Account").

---

## 🏗️ Compute & Storage Architecture

### 🚀 Spark Integration
All data-heavy tasks are offloaded to **PySpark**. The agent itself is a "thin" wrapper that orchestrates Spark jobs. This ensures the system scales to billions of rows.

### 📊 Delta Lake Sidecar Pattern
The agent writes its output to **Delta Lake**. Each run produces:
1.  **Parquet Data:** The `ProfileReport` serialized as a row.
2.  **JSON Index:** A sidecar file (`3e6119e0-fc8e-4aaa-bef8-b65278aa8b31.json`) for fast, human-readable lookup without Spark.

---

[← Back to Main Index](index.md) | [← Return to README](../README.md)
