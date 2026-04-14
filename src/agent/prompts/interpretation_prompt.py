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

### **Your Goal**
Provide a structured interpretation including entity identification, BK confirmation, PII strategy, and DQ flags.
"""
