# How-to: Configure Custom Patterns

**[Home](../index.md) / [How-to Guides](index.md) / Custom Patterns**

The Data Profiling Agent uses a **3-layer hybrid pattern detection** strategy to identify semantic meaning in string columns. This guide explains how to configure and extend these layers.

## 🏗️ The 3-Layer Strategy

1.  **Layer 1: Universal Banking Patterns (Static)**
    Hardcoded in `src/tools/pattern_tool.py`. Includes IBAN, SWIFT/BIC, ISO-8601, and common email formats. These are always active.
2.  **Layer 2: Source-System Patterns (Configurable)**
    Defined in `config/patterns.yaml`. These are unique to your specific core banking or source systems (e.g., `ACC-123456` or `BR-001`).
3.  **Layer 3: Data-Driven Heuristics (Dynamic)**
    Automatic detection based on column naming conventions (`_id`, `_pk`, `_bal`) and statistical properties like uniqueness and cardinality.

## ⚙️ Adding Custom Patterns

To add patterns for a new source system, modify `config/patterns.yaml`:

```yaml
source_system: "my_legacy_banking"
custom_patterns:
  MY_ACCOUNT_ID: "ML-\\d{8}"
  MY_BRANCH_CODE: "B[A-Z]{3}-\\d{2}"
```

### Tips for Better Matching:
*   **Regex Anchors:** Always use `^` and `$` if you want exact matches for the entire column content.
*   **Threshold:** By default, the agent requires **>50% match** in a column to flag a pattern. This is configurable within the `PatternTool.profile` method.

## 🔍 Layer 3 Heuristics (Automatic)

You don't need to configure Layer 3. The agent automatically flags:
*   `LIKELY_KEY`: Columns ending in `_id`, `_pk`, or `_key`.
*   `LIKELY_TEMPORAL`: Columns ending in `_date`, `_dt`, or `_timestamp`.
*   `HIGH_UNIQUENESS_CANDIDATE`: Columns with >95% uniqueness.
*   `LOW_CARDINALITY_CATEGORICAL`: Columns with <50 distinct values representing <10% of total rows.

---
[**❮ Previous: Profile a New Table**](profile-new-data.md) | [**Next: Architecture Deep Dive ➔**](../explanation/architecture.md)
