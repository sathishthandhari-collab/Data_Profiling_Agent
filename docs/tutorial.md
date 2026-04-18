# 🚀 Quickstart Guide

This tutorial will take you from setting up the **Data Profiling Agent** to generating your first AI-driven profile report.

## 📋 Prerequisites

Before you begin, ensure you have:
- Python 3.10+ installed.
- Access to an LLM provider (e.g., Google Gemini, OpenAI, etc.).
- `pyspark` and `delta-spark` dependencies (included in `requirements.txt`).

## 🛠️ Step 1: Environment Setup

Clone the repository and install the dependencies:

```bash
git clone <repository_url>
cd data-profiling-agent
pip install -r requirements.txt
```

Create a `.env` file based on the provided `.env.example`:

```bash
cp .env.example .env
```

Edit the `.env` file to include your API keys and configuration:

```env
GEMINI_API_KEY=your_key_here
LLM_PROVIDER=gemini/gemini-2.5-flash
DATA_PATH=data
API_URL=http://localhost:8000
```

## 🏗️ Step 2: Launch the Services

You can run the agent as a standalone FastAPI service or through the Streamlit UI.

### Option A: Running with Docker (Recommended)

```bash
docker-compose up -d
```
This will start:
- **Agent API:** http://localhost:8000
- **Streamlit UI:** http://localhost:8501

### Option B: Manual Startup

Launch the API:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Launch the UI (in a new terminal):
```bash
streamlit run src.ui/app.py
```

## 📊 Step 3: Profile Your First Table

1. Open the Streamlit UI at http://localhost:8501.
2. Under **Source Connection**, select your connection type (e.g., `delta`, `csv`).
3. Enter the table name or file path.
4. Click **🚀 Trigger Profiling**.
5. Wait for the agent to complete its workflow:
   - **Data Reader:** Loads and samples the data.
   - **Profiler:** Executes specialized tools (Schema, Stats, PII, Patterns, Relations).
   - **Summarizer:** Optimizes the context for the LLM.
   - **Interpreter:** Generates human-readable insights using Gemini.

## 🔄 Batch Profiling

To profile multiple tables at once, you can use the `/profile/batch` endpoint. In the UI, look for the **Batch Mode** toggle or provide a list of configurations via the API:

```bash
curl -X POST "http://localhost:8000/profile/batch" \
     -H "Content-Type: application/json" \
     -d '[
           {"table": "transactions", "connection_type": "delta"},
           {"table": "customers", "connection_type": "delta"}
         ]'
```

---

[← Back to Main Index](./index.md)
