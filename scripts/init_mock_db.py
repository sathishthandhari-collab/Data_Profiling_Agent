import duckdb
from pathlib import Path

def init_db(db_path="data/banking.db", csv_path="data/raw"):
    """
    Initializes a DuckDB database and registers CSVs as tables.
    """
    print(f"🏗️ Initializing DuckDB at {db_path}...")
    
    # Create DB file
    con = duckdb.connect(db_path)
    
    raw_dir = Path(csv_path)
    if not raw_dir.exists():
        print(f"❌ Error: {csv_path} directory does not exist. Run data generation first.")
        return

    # Loop through all CSVs and register as tables
    for csv_file in raw_dir.glob("*.csv"):
        table_name = csv_file.stem
        print(f"📦 Registering table: {table_name} from {csv_file}")
        
        # DuckDB can directly query CSVs (extremely fast)
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_file}')")
    
    # Verify
    tables = con.execute("SHOW TABLES").fetchall()
    print(f"✅ Success! Tables in DB: {[t[0] for t in tables]}")
    con.close()

if __name__ == "__main__":
    init_db()
