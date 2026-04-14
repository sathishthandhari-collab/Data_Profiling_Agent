# Profiling Agent Implementation Plan

This document provides a modular, step-by-step implementation guide for the Profiling Agent, based on the high-level architecture.

## Phase 1: Environment & Project Foundation
**Goal:** Establish the project structure and shared models.

- [ ] **1.1 Project Structure Setup**
    - Create directory tree as defined in `PROFILING_AGENT_PLAN.md`.
    - Initialize `requirements.txt` with Spark, Delta, LangGraph, LangChain, LiteLLM, Pydantic v2, FastAPI, Streamlit, and pytest.
    - Create `.env.example` and `.gitignore`.
- [ ] **1.2 Core Data Models (`src/models/`)**
    - `source_config.py`: Define `SourceConfig` (path, format, options).
    - `profile_report.py`: Implement all Pydantic models (`ColumnSchema`, `StatsProfile`, `BKCandidate`, `FKHint`, `LLMInterpretation`, `ProfileReport`).
- [ ] **1.3 Spark Infrastructure (`src/reader/`)**
    - `spark_session.py`: Factory for `SparkSession` with Delta Lake support.
    - `data_reader.py`: Generic loader for Delta, Parquet, and CSV.

## Phase 2: Data Generation & Mocking (`src/data_gen/`)
**Goal:** Create high-quality synthetic banking data for development and testing.

- [ ] **2.1 Banking Faker**
    - Implement `banking_faker.py` using `Faker` to generate: `accounts`, `transactions`, `customers`, `loans`, `collateral`, `risk_ratings`.
    - Ensure consistent IDs across tables for relation testing.
- [ ] **2.2 Ingestion Script**
    - Script to generate data and save to `data/raw/` (CSV) and `data/delta/`.

## Phase 3: Analytical Tools (`src/tools/`)
**Goal:** Build the specialized tools that the agent will use. Each tool should be a LangChain tool.

- [ ] **3.1 Schema Tool (`schema_tool.py`)**
    - Extract Spark schema, detect PK candidates (uniqueness), and identify format hints.
    - Return `SchemaProfile`.
- [ ] **3.2 Stats Tool (`stats_tool.py`)**
    - Compute null rates, cardinality, min/max/mean, and IQR-based outliers.
    - Return `StatsProfile`.
- [ ] **3.3 Pattern Tool (`pattern_tool.py`)**
    - Regex matching for banking IDs (IBAN, etc.), date format detection, and categorical analysis.
    - Return `PatternProfile`.
- [ ] **3.4 Relation Tool (`relation_tool.py`)**
    - Use HyperLogLog (HLL) sketches (`approx_count_distinct`) to estimate column overlaps without expensive joins.
    - Match high-overlap columns with similar naming patterns for FK hints.
    - Return `RelationProfile`.
- [ ] **3.5 PII Detection Tool (`pii_tool.py`)**
    - Identify sensitive data (Email, SSN, Credit Card, Names).
    - Use a hybrid approach: Spark Regex (fast) + LLM sampling (semantic detection for names).
    - Return `PIIProfile` with `is_pii` and `pii_type` flags.

## Phase 4: LangGraph Agent & LLM (`src/agent/`)
**Goal:** Orchestrate tool execution and LLM interpretation.

- [ ] **4.1 Agent State (`state.py`)**
    - Define `AgentState` Pydantic model to hold Spark DataFrame, SourceConfig, and tool outputs.
- [ ] **4.2 Prompts (`prompts/`)**
    - `system_prompt.py`: General instructions for the profiling expert.
    - `interpretation_prompt.py`: Structured prompt for the LLM to process tool outputs.
- [ ] **4.3 Graph Definition (`profiling_agent.py`)**
    - Define the LangGraph workflow: `Reader -> [Schema, Stats, Pattern, Relation, PII] (Parallel) -> Summarizer -> LLM Interpreter -> Finalizer`.
    - **Summarizer Logic:** Implement a node to filter/rank "interesting" columns for tables > 50 columns to stay within LLM context limits.
- [ ] **4.4 LLM Integration**
    - Configure LiteLLM for local (Ollama) and cloud (OpenAI/Groq) switching.

## Phase 5: Persistence & API (`src/output/`, `src/api/`)
**Goal:** Save the results and expose the agent.

- [ ] **5.1 Delta Writer (`delta_writer.py`)**
    - Logic to serialize `ProfileReport` to JSON and append/upsert to `profiling_reports` Delta table.
- [ ] **5.2 FastAPI (`main.py`)**
    - Endpoint `POST /profile`: Triggers the agent for a given source.
    - Endpoint `GET /report/{id}`: Retrieves a report from Delta.

## Phase 6: UI & Testing (`src/ui/`, `tests/`)
**Goal:** Visualize the results and ensure stability.

- [ ] **6.1 Streamlit App (`ui/app.py`)**
    - Simple dashboard to select tables, trigger profiling, and view the `ProfileReport` + LLM insights.
- [ ] **6.2 Automated Tests**
    - Unit tests for each tool using Spark fixtures.
    - Integration test for the full LangGraph flow.

## Implementation Details for LLM Guidance
- **Strict Typing:** All tools MUST return Pydantic models. No raw dicts.
- **Spark Optimization:** Use Spark built-in functions where possible for speed. Avoid `toPandas()` except for small summaries if absolutely necessary.
- **LLM Context:** When passing tool outputs to the LLM, truncate or summarize if the data is too large, but ensure `BKCandidate` and `FKHint` data is preserved.
- **Error Handling:** The graph should include an "error" node to handle tool failures or data loading issues gracefully.
