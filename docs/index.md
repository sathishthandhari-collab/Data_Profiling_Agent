# Data Profiling Agent Documentation

**[Home](index.md)**

Welcome to the comprehensive documentation for the Data Profiling Agent. This project is the first of six agents in an autonomous data engineering ecosystem, focused on high-scale banking data discovery.

## 🏁 Get Started
Follow our guided path to set up your environment and run your first profiling job.
*   [**Getting Started Tutorial**](tutorials/getting-started.md): Installation to first report.

## 🛠️ How-to Guides
Specific, task-oriented instructions for common scenarios.
*   [**Profile a New Table**](how-to/profile-new-data.md): Connecting to Delta, Parquet, or CSV sources.
*   [**Configure Custom Patterns**](how-to/configure-patterns.md): Adjusting `patterns.yaml` for your specific source systems.

## 🏗️ Architecture & Concepts
Deep dives into the "Why" and "How" of the agent's internal logic.
*   [**Core Architecture**](explanation/architecture.md): LangGraph nodes and state management.
*   [**Spark Tooling**](explanation/spark-tools.md): Understanding the single-pass profiling tools.
*   [**Databricks Deployment**](explanation/databricks-deployment.md): Running the agent on Databricks with Unity Catalog.

## 📚 Technical Reference
Detailed specifications for integration and extension.
*   [**API Reference**](reference/api-reference.md): FastAPI endpoints and request/response models.
*   [**Data Models (Pydantic)**](reference/data-models.md): Detailed schema of the `ProfileReport`.

---
[**Next: Getting Started Tutorial ➔**](tutorials/getting-started.md)
