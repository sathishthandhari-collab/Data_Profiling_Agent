# Tutorial: Your First Profiling Session

In this tutorial, you'll set up the Data Profiling Agent and profile a sample "Accounts" table.

## 🛠 Prerequisites
- Docker and Docker Compose installed.
- Access to an LLM provider (e.g., Google Gemini, OpenAI) or local Ollama.

## 1. Installation
Clone the repository:
```bash
git clone <repo_url>
cd Data_Profiling_Agent
```

## 2. Environment Setup
Create a `.env` file and add your LLM API keys:
```bash
cp .env.example .env
```
Edit `.env`:
```env
LLM_PROVIDER=gemini/gemini-2.5-flash
GOOGLE_API_KEY=your_key_here
```

## 3. Generate Mock Data
Before starting the agent, we need some banking data to profile. Run the ingestion scripts:
```bash
# This creates Delta tables in the data/ folder
python3 scripts/data_gen/ingest_data.py
python3 scripts/init_mock_db.py
```

## 4. Start the Agent
Launch the API and UI services using Docker Compose:
```bash
docker compose up --build
```

## 5. Run Your First Profile
1. Open your browser to `http://localhost:8501` (the Streamlit UI).
2. You should see a list of tables detected in the system.
3. Select the `account` table.
4. Click **Run Profiling**.
5. **Watch the magic:** The agent will load the table via Spark, run its statistical tools, and then send the summary to the LLM for interpretation.

## 6. View the Results
Once the process is complete, the UI will display:
- **Business Summary:** What the table represents (AI-generated).
- **Column Details:** Detailed stats, null rates, and PII alerts.
- **Relationships:** Suggested links to other tables (e.g., `account` → `customer`).

---

## 🎉 Next Steps
Now that you've profiled your first table, check out the [**How-to Guides**](../index.md#️-how-to-guides) to learn how to profile your own custom datasets.
