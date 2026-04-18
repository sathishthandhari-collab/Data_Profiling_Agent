# Explanation: Spark Profiling Tools

**[Home](../index.md) / [Architecture](../index.md#🏗️-architecture--concepts) / Spark Tooling**

The Data Profiling Agent's core "brain" for data analysis consists of five specialized PySpark-based tools. These tools are designed for **high-scale efficiency**, minimizing Spark actions and avoiding redundant data passes.

## 🚀 Efficiency Principle: Single-Pass Aggregation

Instead of running hundreds of `df.select(F.count(...)).collect()` calls, the agent builds a single, massive aggregation expression per table. This allows Spark's Catalyst Optimizer to read the data once and compute everything in a single job.

### 1. Schema Discovery Tool (`SchemaTool`)
*   **What it does:** Extracts data types and nullability.
*   **Unique Feature:** Automatically identifies **Primary Key (PK)** candidates by checking for 100% uniqueness and zero nulls in a single pass using `approx_count_distinct`.

### 2. Stats & Outliers Tool (`StatsTool`)
*   **What it does:** Computes min, max, mean, stddev, and cardinality.
*   **Outlier Detection:** Uses a single `approxQuantile` call to determine IQR (Interquartile Range) and flag columns with statistically significant outliers.

### 3. PII Detection Tool (`PIITool`)
*   **What it does:** Identifies sensitive data (SSN, Email, Name).
*   **Hybrid Approach:** Uses Spark Regex for high-speed scanning of common patterns and **LLM sampling** for semantic detection of person names or complex, non-regexable PII.

### 4. Pattern Matching Tool (`PatternTool`)
*   **What it does:** Detects banking formats (IBAN, Swift, Date).
*   **3-Layer Strategy:** Combines universal patterns, source-system config (`patterns.yaml`), and data-driven heuristics to understand what a column *actually* represents.

### 5. Relation Scoring Tool (`RelationTool`)
*   **What it does:** Discovers potential links between tables.
*   **Containment-Based Scoring:** Uses HLL (HyperLogLog) sketches to calculate the intersection/union between columns across different tables, suggesting potential Foreign Keys (FK) without expensive joins.

## 📊 Summary Logic

For tables with many columns (e.g., >100), the agent's **Summarizer Node** ranks columns based on "interest" (PII detected, high null rate, outliers, PK candidate) to ensure the LLM receives the most critical information first.

---
[**❮ Previous: Core Architecture**](architecture.md) | [**Next: Databricks Deployment ➔**](databricks-deployment.md)
