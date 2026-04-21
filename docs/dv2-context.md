# Data Vault 2.0 Context

Agent 1: The Data Profiling Agent is the critical first step in an autonomous **Data Vault 2.0 (DV2)** automation pipeline. This document explains how profiling outputs feed into downstream modeling and generation agents.

## 🌉 Bridging Raw Data and Business Logic

In a standard Data Vault implementation, significant manual effort is spent analyzing raw source systems to identify **Hubs**, **Links**, and **Satellites**. Agent 1 automates this discovery phase by providing the semantic metadata needed to make these architectural decisions.

### 🧩 How Profiling Feeds the DV2 Modeler

The `ProfileReport` from Agent 1 is the primary input for **Agent 2: The DV2 Modeler**. Here’s how the profiling metrics are utilized:

| Profiling Metric | DV2 Architectural Decision |
| :--- | :--- |
| **Business Key (BK) Candidates** | Used to define **Hubs** and their corresponding Hash Keys. |
| **FK Hints & Relationship Scoring** | Used to identify **Links** between different business entities. |
| **PII Detection** | Signals the need for **Confidential Satellites** or specific encryption rules. |
| **Column Schema & Statistics** | Determines the structure of **Satellites** and tracks history (SCD Type 2). |
| **Suggested Entity Name** | Provides the default business name for the resulting Hub or Link. |

---

## 🏗️ The Automation Pipeline

Agent 1 ensures that the metadata is **governed** and **consistent** before it ever reaches the modeling layer.

1.  **Profiling (Agent 1):** Autonomously analyzes raw data to find BKs and relationships.
2.  **Modeling (Agent 2):** Uses the profile to design the DV2 schema (Hubs, Links, Sats).
3.  **Generation (Agent 3):** Generates `dbt-databricks` code to build the actual vault tables.

## 🎯 Why Profile First?

Without accurate profiling, automated DV2 generation often fails due to:
- **Composite Key Oversights:** Missing a key column needed for uniqueness.
- **Data Quality Issues:** High null rates in potential Business Keys causing primary key violations.
- **Semantic Mismatch:** Misidentifying a surrogate key as a business key.

By using Agent 1, the platform guarantees that the downstream model is built on a foundation of verified data facts rather than assumptions.

---

[← Return to Index](index.md)
