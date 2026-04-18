# Banking AI Agent Platform — High-Level Architecture Plan
> Sathish Thandhari · April 2026 · End-to-End Agentic Data Pipeline Portfolio

---

## 1. Platform Vision

Build a **production-grade, end-to-end agentic data pipeline** on Databricks + Delta Lake using LangGraph and open-source Python. The platform ingests raw synthetic banking data and autonomously:

1. **Profiles** it (schema, stats, patterns, relationships)
2. **Models** it (infers a Data Vault 2.0 entity design)
3. **Builds** the pipeline (generates dbt-databricks vault code)
4. **Validates** it (DQ rules, immutable audit trail)
5. **Orchestrates** everything (stateful LangGraph graph, HITL checkpoints)
6. **Serves** governed answers (NL2SQL on Unity Catalog semantic metrics)

**Raw banking data → governed semantic layer** — fully automated, agent-driven.

---

## 2. System Context

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PLATFORM BOUNDARY                               │
│                                                                        │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐    │
│  │  Synthetic   │    │   Agent      │    │   Databricks Free     │    │
│  │  Banking     │───▶│   Runtime    │◀──▶│   Edition             │    │
│  │  Data (Faker)│    │   (Docker)   │    │   - Unity Catalog     │    │
│  └──────────────┘    └──────┬───────┘    │   - Delta Lake        │    │
│                             │            │   - dbt SQL Warehouse │    │
│                    ┌────────▼────────┐   │   - MLflow            │    │
│                    │  LLM Layer      │   │   - Databricks Jobs   │    │
│                    │  LiteLLM router │   └───────────────────────┘    │
│                    │  - Gemini Flash │                                 │
│                    │    (primary)    │                                 │
│                    │  - Gemini Pro   │                                 │
│                    │    (Agent 2)    │                                 │
│                    │  - Ollama       │                                 │
│                    │    (offline)    │                                 │
│                    └─────────────────┘                                 │
└────────────────────────────────────────────────────────────────────────┘
```

**Architecture Principle:** Docker owns the agent brain. Databricks owns the data layer.

---

## 3. Agent Topology

Six agents connected through a central orchestrator. Each agent is independently deployable via FastAPI and wired together in month 6.

```
                          ┌─────────────────────────┐
                          │   Agent 5 — Orchestrator │
                          │   LangGraph state machine │
                          │   Human-in-the-loop HITL  │
                          └────────────┬────────────┘
                                       │ routes tasks
          ┌────────────────────────────┼──────────────────────────┐
          │                            │                           │
          ▼                            ▼                           ▼
  ┌───────────────┐           ┌────────────────┐         ┌─────────────────┐
  │ Agent 1       │           │ Agent 3        │         │ Agent 6         │
  │ Data Profiler │──────────▶│ DV2.0 Pipeline │         │ Semantic Layer  │
  └───────┬───────┘           │ Builder        │         │ (NL2SQL)        │
          │ ProfileReport     └───────┬────────┘         └─────────────────┘
          ▼                           │ dbt models
  ┌───────────────┐                   ▼
  │ Agent 2       │           ┌────────────────┐
  │ Data Modeling │──────────▶│ Agent 4        │
  │ (DV2.0 spec)  │           │ DQ & Audit     │
  └───────────────┘           └────────────────┘
```

**Data lineage:** Raw tables → ProfileReport (Delta) → DV2.0 Spec → dbt code → validated vault → semantic metrics → NL answers

### Agent Reasoning Patterns

| Agent | Pattern | Rationale |
|---|---|---|
| Agent 1 — Profiling | **ReAct (tool-use)** | Observe data → reason about next tool → act. Four tools in LLM-decided order. |
| Agent 2 — Modeling ★ | **Plan-and-Execute + Reflection** | Multi-step reasoning with self-critique. Hardest task — needs planning loop. |
| Agent 3 — Builder | **Deterministic DAG** | No LLM loop. DV2Spec → template-based code gen. LLM only for edge cases. |
| Agent 4 — DQ & Audit | **Rule engine + LLM remediation** | Validation is deterministic. LLM only invoked on failure to suggest fixes. |
| Agent 5 — Orchestrator | **State Machine (LangGraph)** | Predefined node sequence, conditional edges, HITL interrupts, retry branches. |
| Agent 6 — Semantic | **ReAct (tool-use)** | Intent → metric lookup → SQL gen → observe result → format. |

---

## 4. Infrastructure Architecture

### 4.1 Environment Split

**Tested:** Databricks Free Edition **does** allow outbound HTTP to external APIs (Gemini, OpenAI, Groq all reachable). Both environments are viable runtimes.

| Concern | Docker (primary dev) | Databricks Free (deploy + demo) |
|---|---|---|
| LangGraph agent runtime | ✅ Fast dev loop, no cold start | ✅ Works — can run agents in notebooks/jobs |
| LLM API calls | ✅ Full internet | ✅ Confirmed reachable (tested Apr 2026) |
| PySpark compute | ✅ Configurable RAM/cores | ✅ Serverless (2X-Small warehouse) |
| Unity Catalog | ❌ Not available locally | ✅ Native, managed |
| Delta Lake | ✅ Local file-based Delta | ✅ Managed tables |
| dbt-databricks | ✅ Via docker exec | ✅ Native SQL warehouse |
| MLflow | ❌ Self-hosted setup required | ✅ Native integration |
| Demo surface | Streamlit on :8501 | ✅ Visual notebooks for Loom |

**Dev workflow:** Build and iterate in Docker (instant feedback, no cold starts). Deploy to Databricks for E2E demos and Loom recordings. Both environments run identical agent code.

### 4.2 Docker Services

```yaml
# docker-compose.yml — conceptual layout
services:
  spark-master:   bitnami/spark:3.5     # Spark master
  spark-worker:   bitnami/spark:3.5     # 4 cores, 8 GB RAM
  agent:          ./Dockerfile           # FastAPI on :8000 (all 6 agents)
  ui:             ./Dockerfile           # Streamlit on :8501
```

### 4.3 Databricks ↔ Docker Portability (3-line swap)

| Docker | Databricks Free |
|---|---|
| `SparkSession.builder.master("local[*]")` | Cluster attach via `databricks-connect` |
| Local Delta path (`./data/delta/`) | DBFS or Unity Catalog volume path |
| File watcher / batch read | Auto Loader (`spark.readStream.format("cloudFiles")`) |

All agent logic, Pydantic models, LangGraph graphs, and tool code are **identical** across both environments.

---

## 5. Agent Specifications

### Agent 1 — Data Profiling Agent
**Input:** Source config (table path, format, system name)  
**Output:** Versioned `ProfileReport` written to Delta Lake  
**FastAPI endpoint:** `POST /profile`

```
Raw table (CSV/Parquet/Delta)
        │
        ▼  PySpark reads into DataFrame
┌───────────────────────────────────┐
│        LangGraph Agent Loop        │
│  ┌──────────┐  ┌───────────────┐  │
│  │Schema    │  │Stats Tool     │  │
│  │Tool      │  │null%, card,   │  │
│  │types,PKs │  │distributions  │  │
│  └──────────┘  └───────────────┘  │
│  ┌──────────┐  ┌───────────────┐  │
│  │Pattern   │  │Relation Tool  │  │
│  │Tool      │  │FK hints,      │  │
│  │IBAN/PAN  │  │join scoring   │  │
│  └──────────┘  └───────────────┘  │
│              │                     │
│       LLM Interpretation           │
│  entity names, BK suggestions,     │
│  DQ flags, confidence scores       │
└─────────────────┬─────────────────┘
                  │
                  ▼
           ProfileReport (Pydantic v2)
                  │
                  ▼
         Delta Lake: /profiling_reports
```

**Key models:** `ProfileReport`, `ColumnSchema`, `StatsProfile`, `FKHint`, `LLMInterpretation`

---

### Agent 2 — Data Modeling Agent ★ (Hardest)
**Input:** `ProfileReport` from Agent 1  
**Output:** `DV2Spec` (Pydantic) — entity design, NOT code  
**FastAPI endpoint:** `POST /model`

```
ProfileReport
      │
      ▼
┌──────────────────────────────────┐
│      LangGraph Reasoning Loop     │
│                                   │
│  Step 1: Business entity recog.   │
│  → Which tables are core entities?│
│                                   │
│  Step 2: Business key inference   │
│  → customer_id vs account_id?     │
│                                   │
│  Step 3: Descriptor vs Satellite  │
│  → What changes over time?        │
│                                   │
│  Step 4: Relationship mapping     │
│  → Hub–Link–Satellite topology    │
│  → Non-historized Links?          │
│                                   │
│  Step 5: LLM design review        │
│  → Sanity-check the graph         │
└────────────────┬─────────────────┘
                 │
                 ▼
         DV2Spec (Pydantic v2)
       { hubs, links, satellites,
         pit_tables, business_vault,
         info_mart }
```

**Why separate from Agent 3:** Agent 2 reasons *semantically* (what are the entities?). Agent 3 reasons *structurally* (which dbtvault macro, how to handle effectivity sats?). Two distinct reasoning tasks.

---

### Agent 3 — DV2.0 Pipeline Builder ★
**Input:** `DV2Spec` from Agent 2  
**Output:** dbt-databricks model files + Jinja macros (dbtvault)  
**FastAPI endpoint:** `POST /build`

```
DV2Spec
    │
    ▼
┌────────────────────────────────────┐
│       Code Generation Loop          │
│                                     │
│  Hub generator   → hub_*.sql        │
│  Link generator  → lnk_*.sql        │
│  Sat generator   → sat_*.sql        │
│  PIT generator   → pit_*.sql        │
│  Bridge gen.     → brg_*.sql        │
│  BV generator    → bv_*.sql         │
│  Info mart gen.  → mart_*.sql       │
│                                     │
│  SQLGlot transpilation              │
│  (PySpark fallback if dbt blocked)  │
└────────────────────┬────────────────┘
                     │
                     ▼
            dbt-databricks project/
            ├── models/raw_vault/
            ├── models/business_vault/
            ├── models/info_mart/
            └── dbt_project.yml
```

**DV2.0 Layer Sequence:**
```
Hubs + Links + Satellites → PIT tables → Business Vault → Info Mart
```

---

### Agent 4 — DQ & Audit Agent
**Input:** dbt project from Agent 3 + source data + raw-to-vault mappings  
**Output:** Validation report + reconciliation results + immutable audit log in Delta Lake  
**FastAPI endpoint:** `POST /validate`

```
dbt project + raw tables + vault tables
         │
         ▼
┌─────────────────────────────────┐
│         Validation Pipeline      │
│                                  │
│  Layer 1: dbt tests              │
│  (unique, not_null, FK checks)   │
│                                  │
│  Layer 2: Great Expectations     │
│  (freshness, distribution,       │
│   statistical drift detection)   │
│                                  │
│  Layer 3: pandera                │
│  (column-level schema contracts) │
│                                  │
│  Layer 4: Data Reconciliation    │
│  (raw → vault row count match,   │
│   key completeness checks,       │
│   aggregate value reconciliation,│
│   orphan/duplicate detection)    │
│                                  │
│  Layer 5: LLM remediation        │
│  (generates fix suggestions for  │
│   each failed rule/recon break)  │
└────────────────┬─────────────────┘
                 │
                 ▼
    Audit log → Delta Lake (immutable)
    (BASEL / RBI / SOX requirement)
```

---

### Agent 5 — Orchestrator
**Input:** User trigger (API or Streamlit) + global config  
**Output:** End-to-end pipeline execution, state managed across all agents  
**FastAPI endpoint:** `POST /run`

```
User trigger
     │
     ▼
┌──────────────────────────────────────┐
│        LangGraph State Machine        │
│                                       │
│  State: { source_config,              │
│            profile_report,            │
│            dv2_spec,                  │
│            dbt_project,               │
│            validation_report,         │
│            hitl_approvals,            │
│            retry_counts }             │
│                                       │
│  Node: run_profiler  → Agent 1 API    │
│  Node: run_modeler   → Agent 2 API    │
│  HITL checkpoint: approve DV2 spec    │
│  Node: run_builder   → Agent 3 API    │
│  Node: run_validator → Agent 4 API    │
│  HITL checkpoint: approve audit       │
│  Node: run_semantic  → Agent 6 API    │
│                                       │
│  Retry logic on each node             │
│  Fallback to human review on failure  │
└────────────────┬─────────────────────┘
                 │
                 ▼
         Streamlit UI (port 8501)
         Full run status, HITL prompts,
         live log tail, demo surface
```

**Why only 2 HITL checkpoints:**
- Agent 1 output is observational (describes data, no decisions) → low risk → no HITL
- Agent 3 output is derived from an already-approved DV2Spec → deterministic → no HITL
- Agent 6 runs read-only SQL on governed schema → no side effects → no HITL
- **Agents 2 and 4 are the decision gates** where incorrect output cascades downstream → HITL required

---

### Agent 6 — Semantic Layer Agent
**Input:** Natural language question  
**Output:** SQL, result set, governed metric metadata  
**FastAPI endpoint:** `POST /query`

```
"What is the 90-day NPL ratio by branch?"
         │
         ▼
┌──────────────────────────────────────┐
│       NL → Metric → SQL pipeline      │
│                                       │
│  Step 1: Intent parsing               │
│  LLM identifies metric + dimensions   │
│                                       │
│  Step 2: Metric catalog lookup        │
│  dbt Semantic Layer SDK               │
│  → finds npl_ratio metric             │
│                                       │
│  Step 3: SQL generation               │
│  SQLGlot + Unity Catalog schema       │
│  → governs column access              │
│                                       │
│  Step 4: Execution + formatting       │
│  SQL warehouse → result → LLM formats │
└────────────────┬─────────────────────┘
                 │
                 ▼
         { metric, sql, result_table,
           data_lineage, run_metadata }
```

---

## 6. Data Architecture

### 6.1 Banking Domain — Source Tables (Faker-generated)

| Table | Rows (target) | Snapshots | Domain |
|---|---|---|---|
| `branch` | 200 | 10 monthly | Reference |
| `product` | 500 | 10 monthly | Reference |
| `customer` | 60–100K | 10 monthly | Master |
| `account` | 60–100K | 10 monthly | Master |
| `loan` | 20–30K | 10 monthly | Transactional |
| `deposit` | 40–60K | 10 monthly | Transactional |
| `collateral` | 10–15K | 10 monthly | Supporting |
| `cashflow` | 100–200K | 10 monthly | Fact |

**Realism features:** Nulls (5–15% on non-PK cols), outliers (IQR method), referential integrity violations (1–3% for DQ agent to catch), format variations (IBAN vs local account number formats).

### 6.2 Delta Lake Layer Structure

```
data/
└── delta/
    ├── raw/                        # Landing zone (Agent 1 input)
    │   ├── customer/
    │   ├── account/
    │   ├── loan/
    │   └── ...
    ├── profiling_reports/          # Agent 1 output
    ├── dv2_specs/                  # Agent 2 output
    ├── raw_vault/                  # Agent 3 output (dbt run)
    │   ├── hub_customer/
    │   ├── hub_account/
    │   ├── lnk_customer_account/
    │   ├── sat_customer_details/
    │   └── ...
    ├── business_vault/             # PIT, Bridge tables
    ├── info_mart/                  # Dimensional + fact tables
    └── audit_log/                  # Agent 4 output (immutable)
```

### 6.3 Data Vault 2.0 Entity Map (Banking)

```
Hubs (business keys):
  hub_customer    (customer_id)
  hub_account     (account_id)
  hub_product     (product_code)
  hub_branch      (branch_code)
  hub_loan        (loan_id)
  hub_collateral  (collateral_id)
  hub_employee    (employee_id)

Links (relationships):
  lnk_customer_account      (customer ↔ account)
  lnk_account_product       (account ↔ product)
  lnk_account_branch        (account ↔ branch)
  lnk_loan_customer         (loan ↔ customer)
  lnk_loan_collateral       (loan ↔ collateral)

Satellites (descriptors, historized):
  sat_customer_details      (name, DOB, address, KYC status)
  sat_customer_creditrisk   (credit score, risk rating)
  sat_account_balance       (current balance, status, limits)
  sat_loan_status           (stage, disbursed amt, repayment)
  sat_collateral_valuation  (value, valuation date, type)

PIT Tables:
  pit_customer  (snapshot by customer across all sats)
  pit_account   (snapshot by account across all sats)

Business Vault:
  bv_npl_classification     (non-performing loan flag)
  bv_customer_360           (unified customer view)

Info Mart:
  mart_loan_portfolio        (portfolio analytics)
  mart_branch_performance    (branch KPIs)
  mart_regulatory_report     (BASEL/RBI reporting layer)
```

---

## 7. Shared Technology Stack

| Layer | Library | Version | Purpose |
|---|---|---|---|
| Agent framework | LangGraph | latest | Stateful agent graphs |
| Tools | LangChain | latest | Tool definitions + chains |
| LLM routing | LiteLLM | latest | Gemini / Groq / Ollama / OpenAI switch |
| Compute | PySpark | 3.5.x | DataFrame operations |
| Storage | delta-spark | 3.x | Delta Lake read/write |
| SQL + modeling | SQLGlot | latest | SQL parsing and transpilation |
| DV2.0 codegen | dbtvault | latest | Hub/Link/Sat macros |
| dbt adapter | dbt-databricks | latest | dbt on SQL Warehouse |
| dbt API | dbt-core | latest | Programmatic dbt runs |
| Profiling | ydata-profiling | latest | Statistical baseline |
| DQ rules | Great Expectations | latest | Rule-based validation |
| Schema contracts | pandera | latest | Column-level checks |
| Schemas | Pydantic v2 | 2.x | All agent I/O models |
| Data gen | Faker | 25.x | Synthetic banking data |
| API layer | FastAPI | latest | Agent HTTP interface |
| UI | Streamlit | latest | Demo surface |
| LLM (primary) | Gemini 2.5 Flash | — | Free tier via Google AI Studio (1,500 RPD). Agents 1, 3, 4, 5, 6. |
| LLM (reasoning) | Gemini 2.5 Pro | — | Deep reasoning for Agent 2. User has Gemini Pro subscription with API access. |
| LLM (offline) | Ollama + llama3.1:8b | — | Zero-cost offline fallback when internet unavailable |
| LLM (optional demo) | OpenAI gpt-4o-mini | ~$0.01/run | Optional — only if Gemini output needs polish for Loom recordings |
| Testing | pytest | latest | Unit + integration |
| Docs | mkdocs | latest | Architecture site |

---

## 8. Inter-Agent Contract (Pydantic I/O)

All agents communicate via versioned Pydantic models. No agent reads another agent's Delta tables directly — all reads go through the FastAPI contract.

```
Agent 1 OUT  →  ProfileReport     →  Agent 2 IN
Agent 2 OUT  →  DV2Spec           →  Agent 3 IN
Agent 3 OUT  →  BuildManifest     →  Agent 4 IN
Agent 4 OUT  →  ValidationReport  →  Agent 5 / Orchestrator
Agent 5      →  RunState          →  All agents (shared LangGraph state)
Agent 6 IN   →  NLQuery           →  NL question string
Agent 6 OUT  →  QueryResult       →  SQL + result + lineage
```

**Schema versioning:** Every Pydantic model carries `schema_version: str = "1.0.0"`. Breaking changes require a major version bump and migration script.

**Retrieval posture:** This is a structured data processing pipeline, not a RAG system. No vector DB, no embeddings. Agent 2 uses few-shot DV2.0 examples embedded in the system prompt (~20 static patterns). Agent 6 uses structured API lookup against dbt Semantic Layer / Unity Catalog metadata. All other agents operate on fully specified input.

**Idempotency:** Every run produces a `run_id` (UUID). Agent outputs are partitioned by `run_id` in Delta Lake. Re-running with the same `run_id` overwrites the same partition — safe to retry without accumulating duplicates.

---

## 9. LLM Strategy

### Per-Agent Model Selection

| Agent | Model | Why this model |
|---|---|---|
| Agent 1 — Profiling | **Gemini 2.5 Flash** | Structured I/O (JSON in → JSON out). Speed matters for batch profiling. Reasoning depth not needed — tools do the analysis. |
| Agent 2 — Modeling ★ | **Gemini 2.5 Pro** | Deep multi-step reasoning: entity recognition, BK inference, Hub/Link/Sat classification. Hardest task — needs Pro's reasoning depth. |
| Agent 3 — Builder | **Gemini 2.5 Flash** | Template-based code gen. LLM only for edge cases. Flash is sufficient. |
| Agent 4 — DQ & Audit | **Gemini 2.5 Flash** | Rule evaluation, structured checks. LLM only for remediation suggestions. |
| Agent 5 — Orchestrator | N/A | State machine — no LLM calls. Pure LangGraph routing. |
| Agent 6 — Semantic | **Gemini 2.5 Flash** | Intent parsing + SQL gen. Structured task. Flash handles it well. |

### Fallback Chain

| Priority | Model | Cost | When |
|---|---|---|---|
| **1. Primary** | **Gemini 2.5 Flash** (Google AI Studio free tier) | Free | Default for Agents 1, 3, 4, 6 |
| **2. Reasoning** | **Gemini 2.5 Pro** (Gemini Pro subscription API) | Included in subscription | Agent 2 only — deep reasoning tasks |
| **3. Offline** | Ollama + llama3.1:8b | Free | When internet is unavailable |
| **4. Optional demo** | OpenAI gpt-4o-mini | ~$0.01/run | Only if Gemini output needs extra polish for Loom recordings |

**Switching:** LiteLLM reads `LLM_PROVIDER` from `.env`. No code change required — `litellm.completion(model="gemini/gemini-2.5-flash", ...)` or `litellm.completion(model="gemini/gemini-2.5-pro", ...)` works out of the box.

**Gemini Pro subscription:** User has a Gemini Pro subscription (Google One AI Premium). This provides both chat access at gemini.google.com AND API access via [aistudio.google.com](https://aistudio.google.com). Flash is free for all users; Pro-series models are available through the subscription. API key generated at AI Studio works for both Flash and Pro.

**Prompt design principles:**
- Structured JSON output enforced on all LLM calls (Pydantic validation on response)
- System prompts are versioned files in `src/agent/prompts/`, never inline strings
- Few-shot examples embedded for Agents 2 and 6 (reasoning-heavy tasks)
- Temperature = 0 for code generation tasks, 0.2 for interpretation tasks
- If output fails Pydantic validation, LLM is re-prompted with the validation error (retry node in LangGraph, max 3)

**LLM output safety:**
- No LLM output is executed as code without intermediate validation (Pydantic parse → structural check)
- Agent 3 writes SQL files to disk — execution requires explicit `dbt run`, no auto-execution
- Agent 6 (NL2SQL): generated SQL validated by SQLGlot — only `SELECT` allowed; schema-scoped to Unity Catalog whitelist; results capped at 10K rows

**Key metrics (targets):**

| Metric | Target | Measured by |
|---|---|---|
| E2E pipeline time | <10 min for 100K-row source | RunState timestamps |
| LLM cost per run | $0 (Gemini free tier / Pro subscription) | LiteLLM token tracking |
| Agent success rate | >95% without HITL | Orchestrator error_log |
| DQ pass rate | >90% on first run | Agent 4 ValidationReport |
| NL2SQL accuracy | >80% on 20 test questions | Manual eval vs expected SQL |

**LLM evaluation (Agents 2 & 6):** Golden test set of 10–20 curated input→expected-output pairs per agent. Automated comparison (SQLGlot AST match for SQL, fuzzy match for entity names) + manual review. No LLM-as-judge in v1.

---

## 10. Cross-Cutting Concerns

### 10.1 Observability

| Layer | Tool | Captures |
|---|---|---|
| LLM calls | LangSmith (or `langchain.callbacks` file logger) | Prompt, completion, tokens, latency, cost |
| Agent runs | `structlog` (structured JSON logging) | State transitions, tool invocations, errors, durations |
| Pipeline runs | RunState persisted to Delta Lake | Full trace — agents, timestamps, errors, HITL decisions |
| Spark jobs | Spark UI (port 4040 in Docker) | Job/stage/task metrics, memory, shuffle |

### 10.2 Reliability

**Retry policy:** LLM calls retry 3× with exponential backoff on timeout/rate-limit/malformed-output. Tool execution retries 2× on transient Spark errors. Agent-to-agent (orchestrator) retries 2× on HTTP 5xx. After exhaustion → pipeline pauses → HITL escalation.

**Graceful degradation:** LiteLLM failover chain (Gemini Pro → Gemini Flash → Ollama). Databricks offline → fall back to local Spark + file-based Delta. Agent failure → orchestrator persists RunState checkpoint, surfaces error in Streamlit.

### 10.3 Security Scope

This is a **portfolio project on synthetic data** — no real PII, no multi-tenant access, no production deployment. Auth is API-key-in-`.env`. No encryption at rest. All services on Docker bridge network. Production-grade concerns (RBAC, mTLS, key rotation) are documented in README as architecture discussion, not implemented.

### 10.4 Error Handling

Tools raise typed exceptions (`ToolTimeoutError`, `ToolValidationError`, `ToolExecutionError`). LangGraph nodes catch and decide: retry → fail → escalate. All errors accumulate in `RunState.error_log` with agent_id, timestamp, and stack trace.

| Failure class | Example | Handling |
|---|---|---|
| LLM hallucination | Invents a hub with no source table | Pydantic validation catches → retry with error feedback |
| Tool timeout | PySpark exceeds memory | Fail fast → log → surface to orchestrator |
| Infra failure | Docker OOM, warehouse offline | Retry with backoff → after 3 failures, HITL escalation |
| Contract mismatch | ProfileReport v1.0 vs v1.1 | `strict=False` for minor versions; major = hard fail |

*Detailed retry configs, timeout values, and per-agent failure handling → per-agent specs.*

---

## 11. Repository Structure

### Polyrepo layout — one repo per agent

Each agent is a standalone GitHub repository. This maximises portfolio impact (6 pinned repos vs 1) and makes each agent independently browsable with its own README, Loom demo, and Docker setup.

| Repo | Purpose | Key output |
|---|---|---|
| `Architecture_Agentic_workflow` | High-level plan + per-agent specs (this repo) | plan.md, agent specs |
| `banking-profiling-agent` | Agent 1 — Data Profiling | ProfileReport → Delta |
| `banking-modeling-agent` | Agent 2 — DV2.0 Modeling | DV2Spec (Pydantic) |
| `banking-pipeline-builder` | Agent 3 — dbt Code Generation | dbt-databricks project |
| `banking-dq-audit-agent` | Agent 4 — DQ & Audit | ValidationReport + audit log |
| `banking-orchestrator` | Agent 5 — Pipeline Orchestrator | E2E run + Streamlit UI |
| `banking-semantic-agent` | Agent 6 — NL2SQL Semantic Layer | QueryResult |

**Shared code strategy:** Pydantic contract models (ProfileReport, DV2Spec, etc.) and Spark utilities are copied into each agent repo under `shared/`. At portfolio scale, controlled duplication is simpler than publishing a shared package. If a contract changes, update the downstream agent repos.

### Per-agent repo layout (standard across all agents)

```
banking-profiling-agent/           # Example: Agent 1
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md                       # Includes Loom demo link + Databricks deploy section
├── data/
│   ├── raw/                        # Faker-generated CSVs
│   └── delta/                      # Agent output (Delta Lake)
├── shared/                         # Copied Pydantic contracts + Spark utils
│   ├── models/
│   │   └── profile_report.py
│   └── spark/
│       └── session.py
├── src/
│   ├── data_gen/                   # Faker data generator (Agent 1 only)
│   │   ├── banking_faker.py
│   │   └── schema_config.py
│   ├── tools/                      # Agent-specific tools
│   │   ├── schema_tool.py
│   │   ├── stats_tool.py
│   │   ├── pattern_tool.py
│   │   └── relation_tool.py
│   ├── agent/                      # LangGraph graph + state
│   │   ├── profiling_agent.py
│   │   ├── state.py
│   │   └── prompts/
│   │       ├── system_prompt.py
│   │       └── interpretation_prompt.py
│   ├── api/
│   │   └── main.py                 # FastAPI
│   └── ui/
│       └── app.py                  # Streamlit
├── tests/
│   ├── conftest.py
│   ├── test_schema_tool.py
│   ├── test_stats_tool.py
│   └── fixtures/
│       └── sample_accounts.csv
├── notebooks/
│   └── profiling_demo.ipynb
└── docs/
    ├── architecture.md
    ├── output_schema.md
    └── databricks_deployment.md
```

---

## 12. Build Sequence & Timeline

| Month | Agent | Milestone | Key deliverable |
|---|---|---|---|
| **Apr 2026** | Agent 1 — Profiling | Set up repo, Docker stack, Faker gen, profiling agent working | `ProfileReport` written to Delta, Loom #1 |
| **May–Jun 2026** | Agent 2 — Modeling | DV2 entity reasoning, business key inference, satellite classification | `DV2Spec` Pydantic model, Loom #2 |
| **Jul 2026** | Agent 3 — Builder | dbt-databricks vault code generation from spec | Full dbt project generated end-to-end, Loom #3 |
| **Aug 2026** | Agent 4 — DQ & Audit | GE validations, dbt tests, audit trail | Immutable audit log in Delta, Loom #4 |
| **Sep 2026** | Agent 5 — Orchestrator | LangGraph wiring, HITL checkpoints, Streamlit UI | First full E2E run with all 4 agents, Loom #5 |
| **Oct–Nov 2026** | Agent 6 — Semantic | NL2SQL on Unity Catalog metrics | Live NL query demo, Loom #6 |
| **Dec 2026** | Polish | No new features. README, mkdocs, full E2E video | Public GitHub portfolio + mkdocs site live |
| **Jan 2027** | Networking | LinkedIn content, outreach to Snowflake/DBX SEs | 10 conversations booked |
| **Feb 2027** | Applications | Resume update, system design prep, negotiation research | Active interview pipeline |

**Build rule:** Each agent must have a working demo before the next begins. Orchestrator wired in month 6 only.

---

## 13. Quality Gates

Each agent must pass these gates before the next agent starts:

| Gate | Criterion |
|---|---|
| ✅ Unit tests | `pytest` passes with >80% coverage on core logic |
| ✅ Integration test | Full agent run on 1,000-row sample completes without error |
| ✅ Pydantic validation | Output model validates without exceptions |
| ✅ Delta write | Output persisted to Delta Lake and readable |
| ✅ FastAPI health check | `GET /health` returns 200 with agent metadata |
| ✅ Loom video | 3-minute demo recorded and linked in README |
| ✅ Databricks swap | README documents 3-line change for Databricks deployment |

---

## 14. Key Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Databricks Free blocks LLM API calls | High | All LLM calls run in Docker; Databricks only used for data layer |
| Agent 2 (modeling) takes longer than 2 months | Medium | Hard deadline: ship a v1 spec even if imperfect; iterate in polish phase |
| LangGraph state complexity blows up orchestrator | Medium | Build agents 1–4 with clean FastAPI contracts first; orchestrator is a thin wrapper |
| dbt-databricks SQL warehouse cold starts | Low | Use `docker exec` for dev runs; Databricks only for demo recording |
| LLM output quality insufficient for code gen | Medium | Enforce JSON output schema, validate with Pydantic, add retry node in LangGraph |
| Scope creep to 7th/8th agent | High | Hard rule: no new agents after November 30 |

---

## 15. Interview Narrative

> "I built a multi-agent data platform on Databricks and Delta Lake using LangGraph and open-source Python. The platform takes raw banking source tables and runs them through: a profiling agent that discovers schema, stats, and business key candidates; a modeling agent that infers the Data Vault 2.0 entity design; a pipeline builder that generates dbt-databricks vault code; a DQ and audit agent that validates with immutable audit trails; an orchestrator that wires everything together with human-in-the-loop checkpoints; and a semantic layer agent that answers natural language questions against Unity Catalog metrics. I also have Cortex skills on Snowflake from production work. I'm platform-agnostic."

**Why this works:**
- End-to-end (raw data in → governed semantic layer out)
- Two platforms (Snowflake + Databricks) → doubles addressable market
- Separates modeling from code generation (DV2.0 depth signal)
- Ends with a demo anyone can watch (NL2SQL)
- Immutable audit trail maps to real banking regulatory requirements

---

## 16. Open Questions (to resolve in Week 1)

- [x] ~~**Databricks Free internet test:**~~ Resolved — external APIs reachable (httpbin 200, Gemini 404, OpenAI 401). Both Docker and Databricks are viable runtimes.
- [x] ~~**Monorepo vs polyrepo:**~~ Resolved — polyrepo. One repo per agent for portfolio impact.
- [x] ~~**Gemini Flash vs Groq for Agent 2:**~~ Resolved — **Gemini Pro** for Agent 2 (user has Pro subscription). Flash for all other agents. Groq dropped as primary; Ollama remains offline fallback.
- [ ] **Databricks-connect version:** Which version is compatible with Databricks Free Edition serverless compute? Test in week 1.
- [ ] **Google AI Studio API key setup:** Generate API key at aistudio.google.com, verify it works for both Flash and Pro models via `litellm.completion()` end-to-end.
