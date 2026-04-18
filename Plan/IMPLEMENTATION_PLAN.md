# Profiling Agent — Implementation Plan (v2)

## Status: Existing Codebase Audit

There is a **substantial working codebase** at `S:\DATA\Projects\Agentic-Workflows\Data_Profiling_Agent\`. This is NOT a clean-slate build. The plan is: **copy the working code into the new repo, then improve incrementally.**

### What exists and works

| Component | File | Status | Quality |
|---|---|---|---|
| **Schema Tool** | `src/tools/schema_tool.py` | ✅ Working | Good — single-pass agg, HLL + exact PK verification |
| **Stats Tool** | `src/tools/stats_tool.py` | ✅ Working | Good — single-pass, IQR outliers, Decimal handling |
| **Pattern Tool** | `src/tools/pattern_tool.py` | ✅ Working | Needs update — hardcoded patterns (ACC-, CUST-, LOAN-) make it data-specific. Should be configurable and data-agnostic. |
| **PII Tool** | `src/tools/pii_tool.py` | ✅ Working | Good — regex + column-name heuristic, person-name filter |
| **Relation Tool** | `src/tools/relation_tool.py` | ✅ Working | Good — containment-based FK detection via distinct-join |
| **LangGraph Agent** | `src/agent/profiling_agent.py` | ✅ Working | Good — reader→profiler→summarizer→interpreter→report |
| **Agent State** | `src/agent/state.py` | ✅ Working | Clean TypedDict |
| **Pydantic Models** | `src/models/profile_report.py` | ✅ Working | Complete — ProfileReport, all sub-models |
| **Source Config** | `src/models/source_config.py` | ✅ Working | Supports delta/parquet/csv/duckdb/databricks |
| **Data Reader** | `src/reader/data_reader.py` | ✅ Working | Multi-format, DuckDB fallback |
| **Spark Session** | `src/reader/spark_session.py` | ✅ Working | Factory pattern |
| **Delta Writer** | `src/output/delta_writer.py` | ✅ Working | Delta + sidecar JSON index |
| **FastAPI** | `src/api/main.py` | ✅ Working | POST /profile, GET /report/{id}, threadpool dispatch |
| **Docker** | `docker-compose.yml` | ✅ Working | Spark master/worker + agent + UI + Ollama |
| **Prompts** | `src/agent/prompts/` | Exists | Needs review for Gemini Flash compatibility |
| **Streamlit UI** | `src/ui/` | Exists | Not audited yet |
| **Tests** | `tests/` | Partial | conftest + test_tools only |

### What needs to change for v2

| Area | Change | Why |
|---|---|---|
| **LLM** | Switch from `gemini/gemini-1.5-pro` to `gemini/gemini-2.5-flash` | Flash, not Pro. Agent 1's LLM call is structured JSON classification (tool outputs → interpretation), not deep reasoning. Pro is reserved for Agent 2 (DV2 modeling). See `plan.md` §9 for per-agent model rationale. |
| **Docker** | Remove Ollama service (Gemini Flash is primary) | Simplifies compose; Ollama optional offline fallback |
| **Data source** | Agent connects to Databricks for data (not local copies) | Data lives on Databricks; agent reads remotely via databricks-connect or Delta path |
| **Pattern config** | Make patterns configurable, not hardcoded to specific ID formats | Agent must work with ANY banking data, not just our synthetic data |
| **Multi-table** | Add batch mode: profile all tables in one run | Current code profiles one table per API call |
| **Observability** | Add `structlog` structured logging | Replace `print()` statements |
| **Tests** | Full test coverage for all 5 tools + integration test | Currently only partial |
| **Repo** | New standalone repo (`banking-profiling-agent`) | Polyrepo strategy |
| **Schema version** | Bump ProfileReport to `2.0.0` | Breaking changes from v1 |

---

## Proposed Changes

### Phase 1: Foundation — Repo Setup & Migration

**Goal:** New repo at `S:\DATA\Projects\Agentic-Workflows\Architecture_Agentic_workflow\profiling agent\` with the proven code migrated in.

#### [NEW] Project scaffolding

```
profiling agent/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml                   # For clean imports
├── data/
│   └── delta/                       # Agent output (local ProfileReports)
├── config/
│   └── patterns.yaml                # Source-system patterns (update when data changes)
├── shared/
│   └── models/
│       └── profile_report.py        # Contract model (shared across agents)
├── src/
│   ├── __init__.py
│   ├── reader/
│   │   ├── __init__.py
│   │   ├── spark_session.py
│   │   └── data_reader.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── schema_tool.py
│   │   ├── stats_tool.py
│   │   ├── pattern_tool.py
│   │   ├── relation_tool.py
│   │   └── pii_tool.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── profiling_agent.py
│   │   ├── state.py
│   │   └── prompts/
│   │       ├── system_prompt.py
│   │       └── interpretation_prompt.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── source_config.py
│   │   └── profile_report.py
│   ├── output/
│   │   ├── __init__.py
│   │   └── delta_writer.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py
│   └── ui/
│       ├── __init__.py
│       └── app.py
├── tests/
│   ├── conftest.py
│   ├── test_schema_tool.py
│   ├── test_stats_tool.py
│   ├── test_pattern_tool.py
│   ├── test_relation_tool.py
│   ├── test_pii_tool.py
│   ├── test_agent.py
│   └── fixtures/
│       ├── sample_accounts.csv
│       ├── sample_customers.csv
│       └── sample_loans.csv
├── notebooks/
│   └── profiling_demo.ipynb
└── docs/
    ├── architecture.md
    ├── output_schema.md
    └── databricks_deployment.md
```

#### [MODIFY] requirements.txt — split for environment compatibility
- Pin stable Python 3.11 compatible versions
- Replace `google-generativeai` with LiteLLM-only (LiteLLM handles Gemini natively)
- Remove `duckdb` (data gen is separate; profiling reads Delta/CSV directly)
- Add `structlog` for observability
- Add `tenacity` for LLM retry logic
- Add `pyyaml` for pattern config loading

> **⚠️ Review fix: `databricks-connect` vs `pyspark` conflict**
> These two packages CANNOT coexist — `databricks-connect` replaces `pyspark`.
> Solution: Two requirements files. Code stays identical; only the Spark session factory changes.

**`requirements.txt`** (Docker / local development — uses local Spark):
```
pyspark==3.5.0
delta-spark==3.2.0
langgraph>=0.2.0
langchain>=0.3.0
langchain-community>=0.3.0
litellm>=1.40.0
pydantic>=2.0.0
fastapi>=0.110.0
uvicorn>=0.29.0
streamlit>=1.30.0
pytest>=8.0.0
python-dotenv>=1.0.0
structlog>=24.0.0
httpx>=0.27.0
tenacity>=8.0.0
pyyaml>=6.0.0
```

**`requirements-databricks.txt`** (Databricks remote — replaces pyspark):
```
databricks-connect==14.3.1   # Must match cluster DBR version
# delta-spark NOT needed — Databricks has it built-in
langgraph>=0.2.0
langchain>=0.3.0
langchain-community>=0.3.0
litellm>=1.40.0
pydantic>=2.0.0
fastapi>=0.110.0
uvicorn>=0.29.0
streamlit>=1.30.0
pytest>=8.0.0
python-dotenv>=1.0.0
structlog>=24.0.0
httpx>=0.27.0
tenacity>=8.0.0
pyyaml>=6.0.0
```

#### [MODIFY] .env.example
```
# LLM Configuration
GEMINI_API_KEY=your-key-here
LLM_PROVIDER=gemini/gemini-2.5-flash

# Spark / Data Configuration
SPARK_MASTER=local[*]
DATA_PATH=data

# Databricks connection (for reading source data)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your-token
DATABRICKS_CATALOG=main
DATABRICKS_SCHEMA=banking

# Optional: disable LLM for pure-Spark testing
DISABLE_LLM=false
```

#### [MODIFY] docker-compose.yml
- Remove Ollama service (Gemini Flash over internet is primary)
- Add Spark UI port mapping (4040)
- Simplify to 3 services: spark, agent, ui
- Agent env includes Databricks connection vars

#### [MODIFY] Dockerfile
- Upgrade to Python 3.11-slim

---

### Phase 2: Tools — Migrate & Improve

**Goal:** Copy all 5 tools, apply minor improvements.

#### [MIGRATE] schema_tool.py
- Copy as-is from existing repo — no changes needed
- Already uses single-pass agg + HLL + exact PK verification

#### [MIGRATE] stats_tool.py
- Copy as-is — no changes
- Already handles Decimal coercion, IQR outliers

#### [MODIFY] pattern_tool.py
Rearchitected as a **3-layer hybrid** — config-driven + data-driven + LLM as final judge.

**Layer 1 — Universal banking patterns** (hardcoded, always active):
International standards that apply to any bank worldwide. These live in code, not config.
- IBAN (`^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$`)
- SWIFT/BIC (`^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$`)
- ISO 8601 dates (`^\d{4}-\d{2}-\d{2}`)
- ISO 4217 currency codes (`^[A-Z]{3}$`)
- Email format

**Layer 2 — Source-system patterns** (loaded from `config/patterns.yaml`):
Patterns specific to the source system being profiled. Updated per deployment.
```yaml
# config/patterns.yaml
source_system: "core_banking"
custom_patterns:
  ACCOUNT_ID: "ACC-\\d{6}"
  CUSTOMER_ID: "CUST-\\d{6}"
  LOAN_ID: "LOAN-\\d{6}"
  BRANCH_CODE: "BR-\\d{3}"
```
If no config file exists, only Layer 1 + Layer 3 are used — the agent still works.

**Layer 3 — Data-driven heuristics** (discovery layer, supplements config):
- Column name analysis: `_id` suffix → likely key, `_date` → likely temporal, `_amount` → likely measure
- Uniqueness + non-null scoring: high uniqueness + 0% null → BK candidate
- Low cardinality + string type → likely categorical/status column
- These produce **scored candidates**, not final decisions

**LLM as final judge:** All three layers feed into the LLM interpretation step. The LLM receives pattern matches, heuristic scores, and config-detected IDs — then makes the semantic judgment ("this is a business key", "this is a descriptive attribute", etc.) with confidence scores and reasoning.

This means the agent works out-of-the-box on any banking data (Layers 1+3), but gets sharper when you provide source-system config (Layer 2).

#### [MIGRATE] pii_tool.py
- Copy as-is — no changes
- Person-name column heuristic already avoids false positives

#### [MIGRATE] relation_tool.py
- Copy as-is — no changes
- Containment-based FK detection is solid

---

### Phase 3: Agent — LangGraph + LLM

**Goal:** Migrate the agent, switch to Gemini Flash, improve logging.

#### [MODIFY] profiling_agent.py
1. Change default model from `gemini/gemini-1.5-pro` to `gemini/gemini-2.5-flash`
2. Replace all `print()` calls with `structlog` logging
3. **Add multi-table batch method**: `run_batch(configs: list[SourceConfig])` that profiles all tables **sequentially** and returns `list[ProfileReport]`
4. Add retry logic for LLM calls (max 3 with backoff) — currently no retry on LLM failure
5. Keep the heuristic fallback path (`_fallback_interpretation`) — it's good insurance
6. Update `node_reader` to support reading from Databricks tables (via `config.connection_type="databricks"`)
7. **Review fix: Active sampling for large tables** — In `node_reader`, if `row_count > 10M`, actively sample to 1M rows (not just warn). Tools like PatternTool and RelationTool can crash on unbounded DataFrames. Sampling uses `df.sample(fraction=1_000_000/row_count)` so tools operate on a bounded DF while the full row count is still reported in the ProfileReport.

#### [MODIFY] state.py
- No changes needed — TypedDict is clean

#### [REVIEW] prompts/
- Review `system_prompt.py` and `interpretation_prompt.py` for Gemini Flash compatibility
- Ensure the JSON output format instruction works with Gemini's `response_format`
- Test that Gemini Flash understands the banking domain context
- **Review fix: Prompt resilience for empty tool outputs** — If a tool fails and returns `[]`, the prompt currently injects an empty JSON array. The `INTERPRETATION_PROMPT` must handle this gracefully with explicit instructions like: "If stats_summary is empty, state that statistical profiling was unavailable and do not invent statistics." This prevents LLM hallucination on missing data.

---

### Phase 4: API & Output

**Goal:** Migrate FastAPI endpoints and Delta writer.

#### [MODIFY] main.py (FastAPI)
1. Add `POST /profile/batch` endpoint — accepts list of SourceConfig, returns list of ProfileReport
2. Add `GET /health` endpoint — returns agent metadata (version, model, status)
3. Replace `print()` with structlog
4. Keep `run_in_threadpool` pattern — it's correct

#### [MODIFY] delta_writer.py
- Copy from existing with one addition:
- Sidecar JSON + Delta append pattern is solid — keep as-is for local dev
- **Review fix: Databricks output support** — Add `REPORT_OUTPUT_TABLE` env var (e.g., `main.banking.profiling_reports`). When set, DeltaWriter uses `df.write.format("delta").mode("append").saveAsTable(table_name)` instead of file path. Falls back to local file path when not set. This ensures reports land in Unity Catalog when running on Databricks.

#### [MODIFY] data_reader.py
- Copy from existing, with changes:
- Remove DuckDB fallback path (data gen is separate concern)
- Keep delta/parquet/csv/databricks paths
- **Primary mode:** `connection_type="databricks"` — reads tables from Databricks via `spark.table("catalog.schema.table")`
- **Dev/test fallback:** `connection_type="delta"` or `"csv"` — reads local fixture files
- Databricks connection configured via env vars (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_CATALOG`)

---

### Phase 5: UI & Testing

**Goal:** Streamlit UI for demo + full test coverage.

#### [MODIFY] ui/app.py
- Auto-discover available tables from `data/delta/` directory
- "Profile All" button triggers batch profiling
- Per-table results: schema, stats, patterns, PII, FK hints
- LLM interpretation displayed in a highlighted card
- Errors shown as warnings, not crashes

#### [NEW] Tests
- `test_schema_tool.py` — schema extraction, PK detection, empty DF edge case
- `test_stats_tool.py` — null rates, cardinality, outlier detection, Decimal handling
- `test_pattern_tool.py` — banking ID detection, configurable patterns
- `test_relation_tool.py` — FK hint detection, no self-referential hints
- `test_pii_tool.py` — email/SSN detection, person-name heuristic, false positive avoidance
- `test_agent.py` — full E2E run on fixture data (with `DISABLE_LLM=true`)
- `conftest.py` — shared Spark session fixture, sample DataFrames

---

### Phase 6: Polish & Docs

**Goal:** README, architecture diagram, Databricks deployment guide.

#### [NEW] README.md
- Project description, architecture diagram (ASCII or Mermaid)
- Quick start: `docker-compose up` → hit `POST /profile`
- Loom demo link placeholder
- Databricks deployment section (3-line swap)

#### [NEW] docs/
- `architecture.md` — component diagram, data flow
- `output_schema.md` — ProfileReport field reference
- `databricks_deployment.md` — env var changes for Databricks

---

## Build Sequence

| Step | What | Depends on | Deliverable |
|---|---|---|---|
| 1 | Project scaffolding + requirements + Docker | — | `docker-compose up` boots Spark + agent |
| 2 | Copy & migrate all 5 tools | Step 1 | Tools return Pydantic models from test DataFrames |
| 3 | Copy & migrate agent + prompts | Step 2 | `DISABLE_LLM=true` E2E pass on fixture data |
| 4 | Switch to Gemini Flash + test LLM path | Step 3 | Full E2E with live LLM interpretation |
| 5 | FastAPI endpoints + Delta writer | Step 4 | `POST /profile` returns ProfileReport JSON |
| 6 | Batch profiling (all tables) | Step 5 | `POST /profile/batch` profiles 8 tables |
| 7 | Streamlit UI | Step 6 | Visual demo with table selector |
| 8 | Tests (unit + integration) | Step 5 | `pytest` green |
| 9 | README + docs | Step 7 | Portfolio-ready repo |

---

## Verification Plan

### Automated Tests
```bash
# Unit tests (no Spark, mocked data)
pytest tests/ -v --disable-llm

# Integration test (real Spark, fixture data, LLM disabled)
DISABLE_LLM=true pytest tests/test_agent.py -v

# Full E2E (real Spark, real LLM)
pytest tests/test_agent.py -v
```

### Manual Verification
- `docker-compose up` → Spark UI at :8080, Agent at :8000, Streamlit at :8501
- `POST /profile` with sample accounts table → returns ProfileReport JSON
- `POST /profile/batch` with all 8 tables → returns all 8 reports
- Streamlit UI: select table → see profiling results + LLM interpretation
- Delta Lake: `data/delta/profiling_reports/` contains persisted reports

---

## Resolved Questions

| Question | Answer |
|---|---|
| **Data location** | Data lives on Databricks. Agent connects remotely via databricks-connect. No local data copies. Small fixture CSVs for tests only. |
| **Tool execution** | Sequential. Simpler, easier to debug. |
| **Pattern strategy** | 3-layer hybrid: universal patterns (code) + source-system patterns (config YAML) + data-driven heuristics. LLM is the final judge. |

---

## ⚠️ TODO: When Source Data Changes

If you change the synthetic data (or point the agent at a different banking source system), update:

| What to update | File | Why |
|---|---|---|
| **Source-system patterns** | `config/patterns.yaml` | Add/modify regex patterns for new ID formats (e.g., new account ID format) |
| **Test fixtures** | `tests/fixtures/*.csv` | Fixtures should match the data the agent will actually profile |
| **PII patterns** | `src/tools/pii_tool.py` (PATTERNS dict) | If new PII formats appear (e.g., Aadhaar numbers for Indian banking) |

Layers 1 (universal banking patterns) and 3 (data-driven heuristics) require **no changes** — they work on any data.

---

## Engineering Framework Coverage (8 Dimensions)

### 1. System Design ✅

| Aspect | Where | Detail |
|---|---|---|
| **Agent pattern** | `profiling_agent.py` | **Deterministic DAG** (not ReAct). Nodes execute in fixed order: reader→profiler→summarizer→interpreter. No LLM-decided tool routing — tools run sequentially in `node_profiler`. LLM invoked once at interpretation. |
| **Workflow orchestration** | LangGraph `StateGraph` | Compiled graph with 4 nodes + `END`. No conditional edges — purely linear. |
| **State management** | `state.py` (TypedDict) | All inter-node data flows through typed `AgentState`. DataFrame, tool outputs, and final report all tracked. |
| **Prompt engineering** | `prompts/` | System prompt defines "data profiling expert" persona. Interpretation prompt is structured with JSON placeholders for tool outputs. JSON output enforced via `response_format`. |
| **Few-shot examples** | `interpretation_prompt.py` | **Gap → add:** 1-2 few-shot examples of expected `LLMInterpretation` JSON to guide Gemini Flash. |
| **Failure modes** | `profiling_agent.py` | LLM failure → heuristic fallback. Tool failure → `try/except` with error accumulation. Spark DF unpersisted on completion. |

### 2. Tools + Agent Contract ✅

| Aspect | Where | Detail |
|---|---|---|
| **Tool definitions** | `src/tools/*.py` | 5 tools: Schema, Stats, Pattern, PII, Relation. Each is a static class with `profile()` method. |
| **Input/output schemas** | Pydantic v2 | Every tool returns typed Pydantic models. Input is `(DataFrame, int)` — cached DF + row count. |
| **Input validation** | `SourceConfig` (Pydantic) | API input validated by Pydantic — `connection_type` is `Literal`, `format` is constrained. Invalid payloads rejected at FastAPI. |
| **Tool-level timeouts** | **Gap → add** | Spark job timeout per tool. Thread-based timeout (30s default, configurable). |
| **Resource constraints** | **Gap → add** | Guard: if `row_count > 10M`, warn and sample. RelationTool distinct DF cache — add memory guard. |
| **Error handling** | `profiling_agent.py` | Tool errors accumulated in `state["errors"]`. Non-fatal — agent continues with partial results. |

**Additions for Phase 2:** `@tool_timeout(30s)` decorator, row count guard in `node_reader`, tool contract docs.

### 3. Retrieval Engineering ✅

| Aspect | Where | Detail |
|---|---|---|
| **Retrieval posture** | — | **Not a RAG system.** Retrieves structured data via Spark SQL from Databricks. No embeddings, no chunking, no vector DB. |
| **Context management** | `node_summarizer` | Tables >50 columns: ranks interesting columns (PII, high nulls, outliers, PK candidates), caps at 30 for LLM context window. |
| **Context window optimization** | `node_interpreter` | Tool outputs serialized as compact JSON. Curly braces escaped. Stats truncated. FK hints capped. |
| **Session state** | N/A | Single-shot profiling — stateless. No conversation history or memory system. |

No gaps — retrieval correctly scoped as "Spark data retrieval + LLM context management."

### 4. Reliability Engineering ✅

| Aspect | Where | Detail |
|---|---|---|
| **LLM retry** | `node_interpreter` | **Gap → add:** 3 retries with exponential backoff (1s, 2s, 4s) on timeout/rate-limit/malformed JSON. Currently: single attempt → fallback. |
| **Fallback strategy** | `_fallback_interpretation()` | Heuristic interpretation if LLM fails. Low-confidence (0.25) results from PK columns + high-null stats. |
| **Idempotency** | `ProfileReport.report_id` | UUID per report. Delta writer appends — multiple runs produce separate reports, no overwrites. |
| **Spark timeout** | **Gap → add** | Set `spark.network.timeout=120s`, `spark.sql.broadcastTimeout=120` in `spark_session.py`. |
| **Graceful degradation** | `node_profiler` | RelationTool skips unloadable tables. Tools are independent — one failure doesn't block others. |
| **SLA target** | **Gap → add** | Single table: <60s for 100K rows. Batch (8 tables): <10 min. Timing logged via structlog. |

**Additions for Phase 3:** `tenacity.retry` on LLM calls, structlog timing per node, Spark timeouts.

### 5. Security and Safety ✅

| Aspect | Where | Detail |
|---|---|---|
| **PII detection** | `pii_tool.py` | EMAIL, SSN, PHONE via regex. Person-name via column-name heuristic. Results in `ProfileReport.pii_info`. |
| **LLM output safety** | `node_interpreter` | LLM output → JSON parse → Pydantic validation. No LLM output executed as code. No SQL injection surface. |
| **Prompt injection** | Low risk | Input is `SourceConfig` (structured Pydantic), not free-text. LLM never sees unsanitized user text — only tool output JSON. |
| **API key security** | `.env` + `.gitignore` | Keys in `.env`, never committed. Docker passes as env vars. |
| **Audit logging** | `structlog` | All runs logged: source_table, model, duration, errors, report_id. JSON output. |
| **Data scope** | Portfolio project | Synthetic data only. No real PII, no multi-tenant, no encryption at rest. Production concerns documented in README. |

No critical gaps — appropriate security posture for portfolio project on synthetic data.

### 6. Evaluation and Observability ✅

| Aspect | Where | Detail |
|---|---|---|
| **Unit tests** | `tests/test_*_tool.py` | Per-tool with Spark fixtures. Edge cases: empty DF, all-null columns, wide tables. |
| **Integration test** | `tests/test_agent.py` | Full LangGraph run, `DISABLE_LLM=true`, fixture data. Validates: report produced, Pydantic valid, all fields populated. |
| **E2E test** | `tests/test_agent.py` | Full run with live Gemini Flash. Validates: LLM interpretation structure, confidence > 0, BK candidates present. |
| **LLM output quality** | **Gap → add** | Golden test set: 3-5 curated tables with expected BK candidates. Automated score: precision/recall on BK detection. |
| **Tracing** | `structlog` | JSON logs per node: input size, output size, duration, errors. INFO/WARNING/ERROR levels. |
| **Spark observability** | Spark UI (:4040) | Job/stage/task metrics in Docker. |
| **LLM cost tracking** | **Gap → add** | Log token count + estimated cost per LLM call via `litellm.success_callback`. |

**Additions for Phase 5:** Golden test fixtures, LiteLLM cost callback, `GET /metrics` endpoint.

### 7. Product Thinking ✅

| Aspect | Where | Detail |
|---|---|---|
| **Use case** | — | Data engineer uploads to Databricks → triggers profiling → reviews ProfileReport → passes to modeling agent. |
| **Success metrics** | — | Agent success: >95% without error. BK precision: >80% on golden set. Speed: <60s/100K rows. Cost: $0 (Gemini free tier). |
| **Cost model** | — | Gemini 2.5 Flash free: 1,500 RPD. 8 tables/day = 8 calls = 0.5% quota. Effectively free. |
| **User journey** | Streamlit UI | Select table → Profile → review BKs/PII/DQ → approve → export to modeling agent. |
| **Deployment** | Docker→Databricks | Dev in Docker for speed. Demo on Databricks for portfolio. 3-line env swap. |

### 8. Human-in-the-Loop ❌ Not Required

| Aspect | Detail |
|---|---|
| **Why no HITL** | Agent 1 is **observational** — describes data, doesn't make irreversible decisions. Wrong BK suggestion is just a suggestion with a confidence score. |
| **Downstream safety** | Agent 2 (modeling) treats ProfileReport as input, not truth. Agent 2 HAS its own HITL checkpoint where data engineers review. |
| **Future consideration** | If used standalone, consider Streamlit confirmation before Delta persistence. Not needed for v1 pipeline. |
