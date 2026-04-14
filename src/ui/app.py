import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import os

st.set_page_config(page_title="Data Profiling Agent", layout="wide")

st.title("🏦 Banking Data Profiling Agent")
st.markdown("Analyze LoanIQ-style syndicated lending data using Spark and LLMs.")

# Backend API URL (use container name if running in Docker, else localhost)
API_URL = os.getenv("API_URL", "http://agent:8000")
DATA_ROOT = Path(os.getenv("DATA_PATH", "data"))

# 1. Sidebar - Data Selection
st.sidebar.header("Mock Database Connection")
db_path = DATA_ROOT / "banking.db"
available_tables = []
if db_path.exists():
    import duckdb
    con = duckdb.connect(str(db_path))
    res = con.execute("SHOW TABLES").fetchall()
    available_tables = [t[0] for t in res]
    con.close()

selected_db = st.sidebar.text_input("Database Name", value="banking")
selected_table = st.sidebar.selectbox("Select Table to Profile", available_tables)
source_system = st.sidebar.text_input("Source System", value="LoanIQ")
connection_type = st.sidebar.selectbox("Connection Type", ["duckdb", "databricks"])

if st.sidebar.button("🚀 Trigger Agent"):
    with st.spinner(f"Agent is connecting to {selected_db}.{selected_table}..."):
        payload = {
            "name": selected_table,
            "database": selected_db,
            "table": selected_table,
            "connection_type": connection_type,
            "source_system": source_system
        }
        
        try:
            # Use host.docker.internal if running streamlit locally, else 'agent'
            response = requests.post(f"{API_URL}/profile", json=payload)
            if response.status_code == 200:
                st.session_state["report"] = response.json()
                st.success("Profiling Complete!")
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Connection failed: {str(e)}")

# 2. Main Area - Display Report
if "report" in st.session_state:
    report = st.session_state["report"]
    interp = report.get("interpretation", {})
    
    # Header Info
    col1, col2, col3 = st.columns(3)
    col1.metric("Entity Name (LLM)", interp.get("suggested_entity_name", "Unknown"))
    col2.metric("Row Count", f"{report['row_count']:,}")
    col3.metric("LLM Confidence", f"{interp.get('confidence', 0.0):.2f}")

    # Tabs for different views
    tab_interp, tab_schema, tab_stats, tab_relations = st.tabs([
        "🧠 LLM Interpretation", "📋 Schema", "📊 Stats & PII", "🔗 Relations"
    ])

    with tab_interp:
        st.subheader("Business Key Candidates")
        st.table(pd.DataFrame(interp.get("bk_candidates", [])))
        
        st.subheader("Data Quality Flags")
        for flag in interp.get("dq_flags", []):
            st.warning(flag)
        
        st.subheader("PII Strategy")
        for pii in interp.get("pii_summary", []):
            st.info(pii)

    with tab_schema:
        st.dataframe(pd.DataFrame(report["columns"]))

    with tab_stats:
        stats_df = pd.DataFrame(report["stats"])
        pii_df = pd.DataFrame(report["pii_info"])
        # Merge or show separately
        st.subheader("Column Statistics")
        st.dataframe(stats_df)
        st.subheader("PII Detection")
        st.dataframe(pii_df[pii_df["is_pii"] == True])

    with tab_relations:
        if report.get("fk_hints"):
            st.dataframe(pd.DataFrame(report["fk_hints"]))
        else:
            st.info("No foreign key hints detected.")
else:
    st.info("👈 Select a table and click 'Trigger Agent' to begin.")
