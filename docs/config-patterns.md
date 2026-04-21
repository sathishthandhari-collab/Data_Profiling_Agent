# Configuration Patterns

Agent 1 uses a sophisticated **3-Layer Pattern Strategy** to identify business keys, IDs, and sensitive data formats within banking datasets. This document explains how to configure and extend these patterns.

## 📐 The 3-Layer Strategy

The `PatternTool` operates across three distinct layers of logic to ensure maximum coverage and accuracy:

### 1. Universal Layer (Hardcoded)
These are industry-standard patterns that are globally applicable. They are baked into the core logic of the tool and do not require configuration.
- **IBAN:** International Bank Account Numbers.
- **SWIFT/BIC:** Bank Identifier Codes.
- **Email Addresses:** Standard RFC 5322 patterns.
- **SSN/National IDs:** Common national identification formats.

### 2. Config Layer (YAML-driven)
This layer is source-system specific. Patterns are loaded from `config/patterns.yaml` to match the unique ID formats of different core systems (e.g., Core Banking vs. Loan Origination).

**Example `config/patterns.yaml`:**
```yaml
source_system: "core_banking"
custom_patterns:
  ACCOUNT_ID: "ACC-\\d{6}"
  CUSTOMER_ID: "CUST-\\d{6}"
  LOAN_ID: "LOAN-\\d{6}"
  BRANCH_CODE: "BR-\\d{3}"
```

### 3. Data-Driven Layer (Heuristics)
The tool uses statistical heuristics and metadata analysis to infer patterns when no explicit rule exists:
- **Suffix Analysis:** Columns ending in `_ID`, `_KEY`, `_GUID`, or `_CODE`.
- **Cardinality:** High-uniqueness columns that aren't numeric sequences.
- **Format Consistency:** Identifying repeating string structures (e.g., `XXX-999-XXX`) even if not predefined.

---

## 🛠️ Adding New Patterns

To add a new pattern for a specific source system:

1.  Open `config/patterns.yaml`.
2.  Add a new entry under `custom_patterns` with a descriptive key and a valid **Regex** string.
    - *Note:* Ensure you double-escape backslashes if necessary for YAML/Python compatibility (e.g., `\\d` for a digit).
3.  Restart the agent or re-run the profiling job. The `PatternTool` will automatically pick up the new configuration.

## 🧪 Testing Patterns

Before committing new patterns, it is recommended to test them against a sample of your data using the `test_pattern_tool.py` suite:

```bash
pytest tests/test_pattern_tool.py
```

---

[← Return to Index](index.md)
