# Agent 1: Data Profiling — AI Assistant Guidelines

Welcome, AI Assistant! If you are reading this file, you are assisting with the **Data Profiling Agent (Agent 1)** repository. Please obey all rules in this document when writing code, making architectural suggestions, or debugging.

---

## 1. Global Platform Standards (Apply to all Agents)

### A. Core Technology Stack
- **Data operations:** Use **PySpark** DataFrames (`pyspark.sql`). Never use Pandas or RDDs for core data processing.
- **Storage format:** Delta Lake (`delta-spark`).
- **Data Contracts:** All I/O models must use **Pydantic v2** (`pydantic>=2.0`). Always set strict typing but allow `strict=False` in configurations for minor version flexibility.
- **Logging:** Use `structlog` for structured JSON logging. NEVER use standard `print()` statements.
- **Orchestration:** Use **LangGraph** (`langgraph`) for agent state machines, not standard LangChain chains.
- **API Layer:** Use **FastAPI** (`fastapi`) with `uvicorn`. Ensure LangGraph/Spark operations run securely in non-blocking threads (`run_in_threadpool`).

### B. Infrastructure Context
- The code runs locally in **Docker** but targets **Databricks Free Edition / Serverless** for production/demo via `databricks-connect` and Unity Catalog.
- When generating Spark code, ensure it is compatible with Databricks runtimes (avoid local OS assumptions).

### C. AI Coding Rules
- **No placeholders:** Write complete, functioning, production-ready code. Do not write `# TODO: implement this logic`. 
- **Refactoring:** When modifying a file, preserve existing imports unless they are explicitly dead code.
- **Retrieval Posture:** This platform is a structured data pipeline. **It is NOT a RAG system.** Do not suggest vector databases, sentence embeddings, or text chunking.

---

## 2. Local Agent Context (Agent 1: Profiling)

### A. Mission
You are building **Agent 1**. Its job is to ingest raw banking tables (CSV/Parquet/Delta) and autonomously profile the schema, statistics, patterns, and relationships to produce a single, unified `ProfileReport` (Pydantic).

### B. Architecture Pattern
- Agent 1 uses a **Deterministic DAG** LangGraph pattern, NOT a ReAct (tool-use) pattern.
- The pipeline flows sequentially: `reader` → `profiler` (runs Schema, Stats, Pattern, Relation, PII tools) → `summarizer` → `interpreter`.
- There is NO conditional routing where the LLM decides which tool to run.

### C. Model Strategy
- Agent 1 uses **Gemini 3.0 Flash** (`gemini/gemini-3.0-flash`) via `litellm`.
- Why Flash? The interpretation step requires structured classification, not deep reasoning. The tools do the heavy lifting.

### D. The 3-Layer Pattern Strategy
When working on `PatternTool`, enforce the 3-layer strategy:
1. **Universal Layer:** Hardcoded banking standards (IBAN, SWIFT, emails).
2. **Config Layer:** Loaded from `config/patterns.yaml` (source-system specific like `ACC-\d+`).
3. **Data-Driven Layer:** Heuristics based on column names (e.g. `_id`), uniqueness, and cardinality.

### E. Constraints & Guardrails
- **Row limits:** If a DataFrame exceeds 10M rows, actively sample it (`.sample(fraction=...)`) before feeding it to `PatternTool` or `RelationTool` to prevent OOM errors.
- **Resilience:** All tools must have `@tool_timeout()` decorators. An LLM failure must fall back to `_fallback_interpretation` to ensure the pipeline still returns a valid report, even with lower confidence scores.

### F. Testing Protocol
- Tests live in `tests/` and use `pytest`.
- Integration tests must pass with `DISABLE_LLM=true` to isolate Spark/LangGraph logic from LLM API latency. Use dummy JSON outputs for mocked LLM calls.
