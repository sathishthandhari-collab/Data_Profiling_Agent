import json
import os
from pathlib import Path
from pyspark.sql import Row
from src.reader.spark_session import get_spark_session
from src.models.profile_report import ProfileReport

class DeltaWriter:
    def __init__(self, spark=None, output_path: str | None = None):
        self.spark = spark or get_spark_session()
        data_root = Path(os.getenv("DATA_PATH", "data"))
        # Default to a path under DATA_PATH.
        if output_path is None:
            self.output_path = str(data_root / "delta" / "profiling_reports")
        else:
            p = Path(output_path)
            # Allow passing an explicit absolute path, otherwise anchor under DATA_PATH.
            self.output_path = str(p) if p.is_absolute() else str(data_root / p)

    def write_report(self, report: ProfileReport):
        """
        Serializes the ProfileReport to JSON and saves it to a Delta table.
        """
        print(f"💾 Saving profile report for {report.source_table} to Delta...")
        
        # Convert Pydantic model to JSON string
        report_json = report.model_dump_json()
        
        # Create a Spark Row with core metadata and the full JSON
        row = Row(
            report_id=report.report_id,
            source_table=report.source_table,
            source_system=report.source_system,
            profiled_at=report.profiled_at,
            report_json=report_json
        )
        
        # Create DataFrame and write to Delta
        df = self.spark.createDataFrame([row])
        
        Path(self.output_path).mkdir(parents=True, exist_ok=True)
        df.write.format("delta").mode("append").save(self.output_path)
        print(f"   ✅ Report persisted at {self.output_path}")

    def get_report(self, report_id: str) -> dict:
        """
        Retrieves a specific report by ID.
        """
        if not Path(self.output_path).exists():
            return None
        df = self.spark.read.format("delta").load(self.output_path)
        res = df.filter(df.report_id == report_id).select("report_json").collect()
        
        if res:
            return json.loads(res[0]["report_json"])
        return None
