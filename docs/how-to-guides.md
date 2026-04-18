# 🛠️ How-To Guides

Solve specific tasks and common challenges when using the **Data Profiling Agent**.

## 🎨 Custom Patterns

The agent can detect domain-specific string patterns (e.g., specific account IDs or customer codes). These are configured in `config/patterns.yaml`.

### Step 1: Add your pattern
Edit `config/patterns.yaml`:
```yaml
custom_patterns:
  ACCOUNT_ID: "ACC-\\d{6}"
  LOYALTY_CARD: "LC-\\d{4}-\\d{4}"
```

### Step 2: Restart the Agent
The `PatternTool` loads this configuration at initialization. Restart the API or Docker stack to apply changes.

## 🔗 Data Connections

The `SourceConfig` model determines how the `DataReader` loads your data.

### Delta Lake
Provide the table name. The reader assumes Delta tables are stored in `$DATA_PATH/delta/{table_name}`.
```json
{
  "table": "customer_accounts",
  "connection_type": "delta"
}
```

### CSV or Parquet
Provide the file path relative to `$DATA_PATH`.
```json
{
  "table": "raw_uploads/transactions.csv",
  "connection_type": "csv"
}
```

## ⚙️ LLM Configuration

The agent uses **LiteLLM**, making it compatible with over 100+ providers.

### Switching Models
In your `.env` file, update the `LLM_PROVIDER` variable.

| Provider | Example LLM_PROVIDER |
| --- | --- |
| **Google Gemini** | `gemini/gemini-2.5-flash` |
| **OpenAI GPT-4** | `gpt-4-turbo` |
| **Anthropic Claude** | `claude-3-opus` |

> [!WARNING]
> Ensure the corresponding API keys (e.g., `OPENAI_API_KEY`) are set in your `.env` file.

## 🐳 Running in Docker

For isolated environments, use the provided Docker stack.

### Build and Run
```bash
docker-compose build
docker-compose up -d
```

### Logs & Troubleshooting
```bash
docker-compose logs -f agent
```

---

[← Back to Main Index](./index.md)
