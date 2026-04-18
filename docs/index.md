# 🏦 Data Profiling Agent Documentation

Welcome to the documentation for the **Data Profiling Agent**, an AI-driven system for modern, configuration-driven data profiling using Gemini 2.5 Flash, PySpark, and Delta Lake.

The agent automates the discovery of data patterns, PII detection, relationship inference, and provides LLM-driven interpretations of complex datasets.

---

## 🗺️ Documentation Map

Our documentation is organized following the [Diátaxis framework](https://diataxis.fr/):

### 🚀 [Tutorials](./tutorial.md)
*Learning-oriented: Follow a guided path to get started.*
- **Quickstart Guide:** From zero to your first profile report.
- **Batch Profiling:** Scale your profiling tasks across multiple tables.

### 🛠️ [How-To Guides](./how-to-guides.md)
*Problem-oriented: Solve specific tasks and common challenges.*
- **Custom Patterns:** Adding domain-specific regex patterns for detection.
- **Data Connections:** Connecting to Delta Lake, Parquet, or CSV sources.
- **LLM Configuration:** Swapping models or providers via LiteLLM.
- **Running in Docker:** Deploying the agent and UI stack.

### 📚 [Reference](./api-reference.md)
*Information-oriented: Technical descriptions and API specifications.*
- **API Endpoints:** Detailed documentation of the FastAPI interface.
- **Data Models:** Schema definitions for `SourceConfig` and `ProfileReport`.
- **Tool Logic:** Technical specifications of the underlying profiling tools.

### 🧠 [Explanation](./explanation.md)
*Understanding-oriented: High-level concepts and architecture.*
- **Agent Architecture:** Deep dive into the LangGraph workflow.
- **Interpretation Engine:** How the LLM synthesizes profiling results.
- **Security & Privacy:** PII detection strategies and data sampling.

---

[← Back to README](../README.md)
