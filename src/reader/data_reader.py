from pyspark.sql import DataFrame
from src.reader.spark_session import get_spark_session
from src.models.source_config import SourceConfig
import os
from pathlib import Path
import duckdb

class DataReader:
    def __init__(self, spark=None):
        self.spark = spark or get_spark_session()

    def load_data(self, config: SourceConfig) -> DataFrame:
        """
        Loads data either from:
        - A file path (Delta/Parquet/CSV) when `config.path` is set, or
        - A database/table (DuckDB/Databricks) when `config.path` is not set.

        This keeps the existing UI payload working while supporting the plan's
        "ingest Delta/Parquet/CSV" workflow.
        """
        data_root = Path(os.getenv("DATA_PATH", "data"))

        # 1) Path-based ingestion (preferred when provided)
        if config.path:
            p = Path(config.path)
            fmt = config.format
            if not fmt:
                if p.is_dir():
                    # Heuristic: Delta tables are directories.
                    fmt = "delta"
                else:
                    ext = p.suffix.lower().lstrip(".")
                    fmt = ext if ext in {"parquet", "csv"} else None

            if fmt in {"delta"}:
                return self.spark.read.format("delta").load(str(p))
            if fmt in {"parquet"}:
                return self.spark.read.parquet(str(p))
            if fmt in {"csv"}:
                opts = {"header": "true", "inferSchema": "true"}
                opts.update(config.options or {})
                return self.spark.read.options(**opts).csv(str(p))

            raise ValueError(f"Unsupported format for path ingestion: format={config.format!r}, path={config.path!r}")

        # 2) DB/table ingestion (current Streamlit contract)
        print(f"📡 Connecting to {config.connection_type} source: {config.database}.{config.table}")
        
        if config.connection_type == "duckdb":
            # Prototype behavior: prefer the curated Delta version if present.
            delta_table_path = data_root / "delta" / config.table
            if delta_table_path.exists():
                return self.spark.read.format("delta").load(str(delta_table_path))

            # Fallback: read directly from DuckDB into Spark (works for smallish tables).
            db_path = data_root / f"{config.database}.db"
            if not db_path.exists():
                raise FileNotFoundError(
                    f"DuckDB file not found at {db_path}. "
                    f"Also no Delta table found at {delta_table_path}."
                )

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                pdf = con.execute(f"SELECT * FROM {config.table}").df()
            finally:
                con.close()

            return self.spark.createDataFrame(pdf)
        
        elif config.connection_type == "databricks":
            # In Databricks, we'd simply use:
            return self.spark.table(f"{config.database}.{config.table}")

        # Convenience: allow specifying "delta/parquet/csv" without a path, using DATA_PATH.
        elif config.connection_type in {"delta", "parquet", "csv"}:
            base = data_root / config.connection_type
            p = base / config.table
            if config.connection_type == "csv":
                p = p.with_suffix(".csv") if p.suffix.lower() != ".csv" else p
                opts = {"header": "true", "inferSchema": "true"}
                opts.update(config.options or {})
                return self.spark.read.options(**opts).csv(str(p))
            if config.connection_type == "parquet":
                return self.spark.read.parquet(str(p))
            return self.spark.read.format("delta").load(str(p))
            
        else:
            raise ValueError(f"Connection type {config.connection_type} not implemented.")
