# Profiling agent — plan

## Overview

The profiling agent is the **entry point** of the banking data platform. It takes raw banking
source tables (accounts, transactions, customers, loans, collateral, risk ratings) and produces
a structured `ProfileReport` — a Pydantic model that downstream agents (starting with the
modeling agent) consume to make design decisions.

The agent does not just run statistics. It **interprets** them using an LLM to surface business
key candidates, entity hints, data quality flags, and relationship hypotheses. This is what
separates it from a plain ydata-profiling run.

---

## Goals

- Ingest any banking Delta table, Parquet file, or CSV without manual schema configuration
- Detect column types, null rates, cardinality, distributions, and outlier presence
- Identify business key candidates (account_id, customer_id, loan_id) via regex + uniqueness heuristics
- Surface foreign key hints and potential join columns across tables
- Produce a structured, versioned `ProfileReport` persisted to Delta Lake
- Feed that report directly to the modeling agent as its input

---

## Architecture — components

### 1. Data reader layer
Responsible for loading source data into Spark DataFrames regardless of format.

- **PySpark** — primary compute engine
- **delta-spark** — reads Delta Lake tables (local Docker volume)
- **Supports**: Delta table path, Parquet directory, CSV with delimiter config
- **Schema inference**: Spark native `inferSchema=True` + override config

### 2. LangGraph agent
The orchestration layer. Routes tool calls, manages state between steps, handles retries.

- **LangGraph** — stateful graph of tool calls
- **LangChain** — tool definitions, prompt chaining
- **LiteLLM** — LLM router (Ollama locally, OpenAI/Groq in demo mode)
- **Pydantic v2** — state schema and output validation

The agent runs four tools in sequence. Each tool returns a typed Pydantic model. All four
outputs are passed together to the LLM interpretation step.

### 3. Tool: Schema tool
- Extracts column names, Spark data types, nullable flags
- Identifies candidate primary keys (100% unique, non-null columns)
- Detects format hints (timestamp columns, currency columns, boolean-like int columns)
- Output: `SchemaProfile` Pydantic model

### 4. Tool: Stats tool
- Computes null percentage per column
- Computes cardinality (distinct count / total rows)
- Computes min, max, mean, stddev for numeric columns
- Detects outlier presence using IQR method
- Output: `StatsProfile` Pydantic model

### 5. Tool: Pattern tool
- Regex scanning for known banking ID patterns (IBAN, account numbers, SWIFT codes, PAN)
- Date format detection (DD-MM-YYYY vs ISO 8601 vs epoch)
- Categorical code detection (status columns, type columns with low cardinality)
- Business key scoring: combines uniqueness + regex match + naming convention
- Output: `PatternProfile` Pydantic model

### 6. Tool: Relation tool
- Cross-table FK hint detection: same column name + matching cardinality ratio
- Referential integrity sample check: does col A values exist in col B?
- Join candidate scoring
- Output: `RelationProfile` Pydantic model

### 7. LLM interpretation layer
Receives all four Pydantic tool outputs as context. Sends a structured prompt to the LLM.

**What the LLM does:**
- Suggests human-readable entity names for each table (e.g. `acct_master` → `Account`)
- Confirms or overrides the BK candidate shortlist with reasoning
- Flags columns that look like they carry PII
- Surfaces data quality concerns (e.g. "loan_amount has 12% nulls — flag for DQ agent")
- Assigns a confidence score (0.0–1.0) to each entity and BK suggestion
- Output: `LLMInterpretation` Pydantic model

### 8. Output: ProfileReport
Top-level Pydantic model wrapping all tool outputs + LLM interpretation.
Serialised to JSON and written to a Delta Lake table (`profiling_reports`).
Also exposed via FastAPI endpoint for the orchestrator to consume.

---

## Intended workflow

```
1. Source config provided (table path, format, source system name)
       ↓
2. Data reader loads DataFrame into Spark
       ↓
3. LangGraph agent begins — initialises state
       ↓
4. Schema tool runs     → SchemaProfile
5. Stats tool runs      → StatsProfile
6. Pattern tool runs    → PatternProfile
7. Relation tool runs   → RelationProfile
       ↓
8. All four outputs passed to LLM interpretation step
       ↓
9. LLM returns entity hints, BK suggestions, DQ flags, confidence scores
       ↓
10. ProfileReport assembled and validated (Pydantic)
       ↓
11. ProfileReport written to Delta Lake (profiling_reports table)
12. ProfileReport returned via FastAPI → consumed by modeling agent
```

---

## Pydantic output schema

```python
class ColumnSchema(BaseModel):
    name: str
    spark_type: str
    nullable: bool
    is_pk_candidate: bool
    uniqueness_ratio: float

class StatsProfile(BaseModel):
    column: str
    null_pct: float
    cardinality: int
    min_val: Optional[Any]
    max_val: Optional[Any]
    has_outliers: bool

class BKCandidate(BaseModel):
    column: str
    confidence: float          # 0.0 – 1.0
    reasoning: str

class FKHint(BaseModel):
    source_col: str
    target_table: str
    target_col: str
    match_ratio: float

class LLMInterpretation(BaseModel):
    suggested_entity_name: str
    bk_candidates: list[BKCandidate]
    pii_columns: list[str]
    dq_flags: list[str]
    confidence: float

class ProfileReport(BaseModel):
    report_id: str             # UUID
    source_table: str
    source_system: str         # e.g. "core_banking", "loan_origination"
    profiled_at: datetime
    row_count: int
    columns: list[ColumnSchema]
    stats: list[StatsProfile]
    fk_hints: list[FKHint]
    interpretation: LLMInterpretation
    schema_version: str = "1.0.0"
```

---

## Repo structure

```
banking-profiling-agent/
│
├── docker-compose.yml              # Spark + Delta + agent + Streamlit services
├── Dockerfile                      # Agent service image
├── requirements.txt
├── .env.example                    # LLM API keys, Spark config
├── README.md
│
├── data/
│   ├── raw/                        # Faker-generated CSVs land here
│   └── delta/                      # Local Delta Lake tables
│       └── profiling_reports/      # Output persisted here
│
├── src/
│   │
│   ├── data_gen/
│   │   ├── __init__.py
│   │   ├── banking_faker.py        # Synthetic banking data generator
│   │   └── schema_config.py        # Table definitions for Faker
│   │
│   ├── reader/
│   │   ├── __init__.py
│   │   ├── spark_session.py        # SparkSession factory (local Docker mode)
│   │   └── data_reader.py          # Delta / Parquet / CSV loader
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── schema_tool.py          # LangChain tool — SchemaProfile
│   │   ├── stats_tool.py           # LangChain tool — StatsProfile
│   │   ├── pattern_tool.py         # LangChain tool — PatternProfile
│   │   └── relation_tool.py        # LangChain tool — RelationProfile
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── profiling_agent.py      # LangGraph graph definition
│   │   ├── state.py                # AgentState Pydantic model
│   │   └── prompts/
│   │       ├── system_prompt.py
│   │       └── interpretation_prompt.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── profile_report.py       # ProfileReport and all sub-models
│   │   └── source_config.py        # SourceConfig input model
│   │
│   ├── output/
│   │   ├── __init__.py
│   │   └── delta_writer.py         # Writes ProfileReport to Delta table
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py                 # FastAPI — POST /profile, GET /report/{id}
│   │
│   └── ui/
│       ├── __init__.py
│       └── app.py                  # Streamlit demo UI
│
├── tests/
│   ├── conftest.py                 # Spark session fixture
│   ├── test_reader.py
│   ├── test_schema_tool.py
│   ├── test_stats_tool.py
│   ├── test_pattern_tool.py
│   ├── test_relation_tool.py
│   ├── test_agent.py               # End-to-end agent run on fixture data
│   └── fixtures/
│       └── sample_accounts.csv     # Small fixture for fast tests
│
├── notebooks/
│   └── profiling_demo.ipynb        # Walk-through notebook for the Loom recording
│
└── docs/
    ├── architecture.md             # This diagram in text form
    ├── output_schema.md            # ProfileReport field reference
    └── databricks_deployment.md    # 3-step guide to point at real Databricks
```

---

## Docker services (`docker-compose.yml`)

| Service | Image | Purpose |
|---|---|---|
| `spark-master` | bitnami/spark:3.5 | Spark master node |
| `spark-worker` | bitnami/spark:3.5 | Single worker (4 cores, 8GB RAM) |
| `agent` | ./Dockerfile | Profiling agent + FastAPI on port 8000 |
| `ui` | ./Dockerfile | Streamlit on port 8501 |

Delta Lake files written to a shared Docker volume mounted at `/data/delta`.

---

## Tech stack — full list

| Layer | Library | Version | Purpose |
|---|---|---|---|
| Compute | PySpark | 3.5.x | DataFrame operations |
| Storage | delta-spark | 3.x | Delta Lake read/write |
| Agent | LangGraph | 0.2.x | Stateful agent graph |
| Tools | LangChain | 0.3.x | Tool definitions |
| LLM routing | LiteLLM | latest | Ollama local / OpenAI / Groq |
| Profiling | ydata-profiling | 4.x | Statistical baseline |
| Validation | Pydantic v2 | 2.x | All schemas |
| Patterns | pandera | 0.x | Column-level validation |
| Data gen | Faker | 25.x | Synthetic banking data |
| API | FastAPI | 0.11x | Agent HTTP interface |
| UI | Streamlit | 1.3x | Demo front-end |
| Testing | pytest | 7.x | Unit + integration tests |

---

## LLM strategy

- **Local dev**: Ollama + `llama3.1:8b` — zero cost, runs in Docker
- **Demo recording**: OpenAI `gpt-4o-mini` or Groq `llama-3.1-70b` — fast, cheap
- **LiteLLM** routes between them via `.env` flag — no code change needed

---

## Key deliverables for this agent

- [ ] `banking_faker.py` — generates 6 banking tables, ~50K rows each
- [ ] All 4 tools working independently with unit tests
- [ ] Full LangGraph agent running end-to-end on fixture data
- [ ] `ProfileReport` written to Delta and readable by the next agent
- [ ] FastAPI endpoint returning `ProfileReport` as JSON
- [ ] Streamlit UI showing profiling results per table
- [ ] Loom demo: raw CSV in → ProfileReport out, ~3 minutes

---

## Databricks deployment note

To run this agent on real Databricks instead of Docker, three changes are needed:

1. Replace `SparkSession.builder.master("local[*]")` with Databricks cluster attach
2. Replace local Delta path (`/data/delta`) with DBFS or Unity Catalog volume path
3. Replace file-watcher ingestion with Auto Loader (`spark.readStream.format("cloudFiles")`)

All agent logic, tool code, Pydantic models, and LangGraph graph are identical.
See `docs/databricks_deployment.md` for the full config diff.
