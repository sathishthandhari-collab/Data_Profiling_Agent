INTERPRETATION_PROMPT = """
Analyze the following data profiling metadata for the table: {table_name}
Source System: {source_system}

### **Metadata Overview**
- Row Count: {row_count}
- PK Candidates (Schema Tool): {pk_candidates}
- Statistical Profile (Summarized): {stats_summary}
- PII Findings: {pii_findings}
- Pattern Tool Detections: {pattern_detections}
- FK Relationship Hints: {fk_hints}

### **Resilience & Missing Data**
- If `stats_summary` is empty or missing, explicitly state that statistical profiling was unavailable and do not invent statistics.
- Base all assertions directly on the provided metadata.

### **Your Goal**
Provide a structured interpretation including entity identification, BK confirmation, PII strategy, and DQ flags. 

Return an object strictly matching this JSON structure:
{{
  "suggested_entity_name": "string",
  "bk_candidates": [
    {{ "column": "string", "confidence": 0.9, "reasoning": "string" }}
  ],
  "pii_summary": ["string"],
  "dq_flags": ["string"],
  "confidence": 0.8
}}

### **Example Output Strategy**
```json
{{
  "suggested_entity_name": "Customer",
  "bk_candidates": [
    {{ "column": "customer_id", "confidence": 0.95, "reasoning": "High uniqueness score and detected 'CUST-' pattern." }}
  ],
  "pii_summary": ["email: detected EMAIL signature with high confidence.", "social_security: high likelihood of SSN numbers."],
  "dq_flags": ["'account_balance' shows significant IQR outliers.", "'address_2' has high null rate (40%)."],
  "confidence": 0.85
}}
```
"""
