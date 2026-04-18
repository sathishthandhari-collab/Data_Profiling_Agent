import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import os

st.set_page_config(page_title="Data Profiling Agent v2", layout="wide")

st.title("🏦 Banking Data Profiling Agent v2")
st.markdown("Modern, configuration-driven data profiling using Gemini 2.5 Flash.")

# Backend API URL
API_URL = os.getenv("API_URL", "http://agent:8000")
DATA_ROOT = Path(os.getenv("DATA_PATH", "data"))

# 1. Sidebar - Data Selection
st.sidebar.header("Source Connection")

connection_type = st.sidebar.selectbox("Connection Type", ["delta", "databricks", "csv", "parquet"])

available_tables = []
if connection_type == "delta":
    delta_base = DATA_ROOT / "delta"
    if delta_base.exists():
        available_tables = [d.name for d in delta_base.iterdir() if d.is_dir() and d.name != "profiling_reports" and not d.name.endswith("_index")]

selected_db = st.sidebar.text_input("Database/Catalog", value="banking")
selected_table = st.sidebar.selectbox("Select Table", available_tables if available_tables else ["accounts", "customers", "loans"])
source_system = st.sidebar.text_input("Source System", value="core_banking")

col1, col2 = st.sidebar.columns(2)
if col1.button("🚀 Profile Table"):
    with st.spinner(f"Profiling {selected_table}..."):
        payload = {
            "name": selected_table,
            "database": selected_db,
            "table": selected_table,
            "connection_type": connection_type,
            "source_system": source_system
        }
        try:
            response = requests.post(f"{API_URL}/profile", json=payload)
            if response.status_code == 200:
                st.session_state["report"] = response.json()
                st.success("Profiling Complete!")
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Connection failed: {str(e)}")

if col2.button("📦 Profile All"):
    with st.spinner("Batch profiling all tables..."):
        configs = [
            {
                "name": t,
                "database": selected_db,
                "table": t,
                "connection_type": connection_type,
                "source_system": source_system
            } for t in available_tables
        ]
        try:
            response = requests.post(f"{API_URL}/profile/batch", json=configs)
            if response.status_code == 200:
                st.session_state["batch_reports"] = response.json()
                st.success(f"Batch Profiling Complete! ({len(response.json())} tables)")
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Connection failed: {str(e)}")

# 2. Main Area - Display Report
if "report" in st.session_state:
    report = st.session_state["report"]
    interp = report.get("interpretation") or {}
    
    st.subheader(f"Results: {report['source_table']}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Entity (LLM)", interp.get("suggested_entity_name", "Unknown"))
    col2.metric("Row Count", f"{report['row_count']:,}")
    col3.metric("LLM Confidence", f"{interp.get('confidence', 0.0):.2f}")
    col4.metric("Schema Version", report.get("schema_version", "1.1.0"))

    tab_interp, tab_schema, tab_stats, tab_patterns, tab_relations = st.tabs([
        "🧠 LLM Interpretation", "📋 Schema", "📊 Statistics", "🎯 Patterns & PII", "🔗 Relations"
    ])

    with tab_interp:
        st.subheader("Business Key Candidates")
        if interp.get("bk_candidates"):
            st.table(pd.DataFrame(interp["bk_candidates"]))
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Data Quality Flags")
            for flag in interp.get("dq_flags", []):
                st.warning(flag)
        with c2:
            st.subheader("PII Strategy")
            for pii in interp.get("pii_summary", []):
                st.info(pii)

    with tab_schema:
        st.dataframe(pd.DataFrame(report["columns"]), use_container_width=True)

    with tab_stats:
        st.dataframe(pd.DataFrame(report["stats"]), use_container_width=True)

    with tab_patterns:
        col_pii, col_patt = st.columns(2)
        with col_pii:
            st.subheader("PII Detection")
            pii_df = pd.DataFrame(report["pii_info"])
            if not pii_df.empty:
                st.dataframe(pii_df[pii_df["is_pii"] == True], use_container_width=True)
        with col_patt:
            st.subheader("Pattern Detections")
            st.json(report.get("detected_patterns", {}))

    with tab_relations:
        if report.get("fk_hints"):
            st.dataframe(pd.DataFrame(report["fk_hints"]), use_container_width=True)
        else:
            st.info("No foreign key hints detected.")

elif "batch_reports" in st.session_state:
    st.subheader("Batch Profiling Summary")
    reports = st.session_state["batch_reports"]
    summary_data = []
    for r in reports:
        interp = r.get("interpretation") or {}
        summary_data.append({
            "Table": r["source_table"],
            "Entity": interp.get("suggested_entity_name"),
            "Rows": r["row_count"],
            "BK Confidence": interp.get("confidence")
        })
    st.table(pd.DataFrame(summary_data))
    st.info("Select a single table to see full details.")

else:
    st.info("👈 Select connection and click 'Profile Table' to begin.")
