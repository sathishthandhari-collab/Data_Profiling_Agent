import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.data_gen.banking_faker import BankingDataGenerator
from src.reader.spark_session import get_spark_session

def main():
    print("🚀 Starting Data Generation...")
    
    # Initialize Generator
    gen = BankingDataGenerator(seed=42)
    
    # Request volumes (scaling main tables to 50k-80k)
    counts = {
        "branch": 5,
        "product": 5,
        "customer": 1000,
        "account": 5000,
        "loan": 4000,
        "collateral": 1500,
        "cashflow": 10000,  
        "deposit": 1000
    }
    
    data_dict = gen.generate_all(counts)
    
    # Ensure directories exist
    raw_path = Path("data/raw")
    delta_path = Path("data/delta")
    raw_path.mkdir(parents=True, exist_ok=True)
    delta_path.mkdir(parents=True, exist_ok=True)
    
    # Get Spark Session
    spark = get_spark_session("DataIngestion")
    
    for table_name, df in data_dict.items():
        print(f"📦 Processing {table_name} ({len(df)} rows)...")
        
        # 1. Save as CSV (Raw)
        csv_file = raw_path / f"{table_name}.csv"
        df.to_csv(csv_file, index=False)
        print(f"   ✅ Saved to {csv_file}")
        
        # 2. Save as Delta (Curated)
        spark_df = spark.createDataFrame(df)
        delta_table_path = str(delta_path / table_name)
        spark_df.write.format("delta").mode("overwrite").save(delta_table_path)
        print(f"   ✅ Saved to {delta_table_path}")

    print("\n✨ Data Generation and Ingestion Complete!")

if __name__ == "__main__":
    main()
