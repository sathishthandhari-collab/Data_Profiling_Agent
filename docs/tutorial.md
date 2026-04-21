# Tutorial: Profile Your First Table

In this tutorial, we'll walk through a complete data profiling workflow. By the end, you'll have a fully generated **ProfileReport** for a synthetic banking accounts table.

## 🏃 Prerequisites

1.  **Clone the repository.**
2.  **Edit your `.env` file** to add your `GEMINI_API_KEY`.
3.  **Start the services:**
    ```bash
    docker-compose up --build
    ```

## 📝 Step 1: Ingest Data

First, we'll use the Faker data generator (if available) to create sample banking data.

```bash
# Run the data generator script (if you have it)
python src/data_gen/banking_faker.py --rows 1000
```

This will create a Delta table at `data/delta/accounts`.

## 🚀 Step 2: Trigger the Profiling Agent

Use **cURL** or the FastAPI Swagger UI to trigger the profiling process.

```bash
curl -X POST "http://localhost:8000/profile" \
     -H "Content-Type: application/json" \
     -d '{
           "system_name": "faker_banking",
           "table_name": "accounts",
           "path": "/data/delta/accounts",
           "format": "delta",
           "connection_type": "local"
         }'
```

The agent will:
1.  **Read the Delta table** using PySpark.
2.  **Execute the 5-tool profiling suite** (Schema, Stats, Patterns, PII, Relations).
3.  **Consult the LLM (Gemini Flash)** to interpret the results.
4.  **Write the final report** back to Delta Lake.

## 📊 Step 3: Review Results in Streamlit

Open your browser and navigate to:
**[http://localhost:8501](http://localhost:8501)**

1.  **Select the "Accounts" table** from the sidebar.
2.  **Review the Schema tab** for data types and PK candidates.
3.  **Check the Stats tab** for null rates and outliers.
4.  **Examine the "LLM Insights" card** to see the agent's business key (BK) and entity suggestions.

---

[← Back to Main Index](index.md) | [← Return to README](../README.md)
