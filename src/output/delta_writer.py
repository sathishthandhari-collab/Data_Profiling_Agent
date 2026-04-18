import json
import os
import structlog
from pathlib import Path
from pyspark.sql import Row
from src.reader.spark_session import get_spark_session
from src.models.profile_report import ProfileReport

logger = structlog.get_logger(__name__)

class DeltaWriter:
    def __init__(self, spark=None, output_path: str | None = None):
        self.spark = spark or get_spark_session()
        data_root = Path(os.getenv("DATA_PATH", "data"))
        
        # Databricks output table (e.g., main.banking.profiling_reports)
        self.output_table = os.getenv("REPORT_OUTPUT_TABLE")
        
        if output_path is None:
            self.output_path = str(data_root / "delta" / "profiling_reports")
        else:
            p = Path(output_path)
            self.output_path = str(p) if p.is_absolute() else str(data_root / p)

        self._sidecar_dir = Path(self.output_path + "_index")

    def write_report(self, report: ProfileReport):
        """
        Serializes the ProfileReport to JSON and saves it to a Delta table or Databricks table.
        """
        logger.info("saving_profile_report", table=report.source_table, id=report.report_id)

        report_json = report.model_dump_json()

        # 1) Sidecar JSON for fast lookup
        try:
            self._sidecar_dir.mkdir(parents=True, exist_ok=True)
            (self._sidecar_dir / f"{report.report_id}.json").write_text(report_json, encoding="utf-8")
        except Exception as e:
            logger.warning("sidecar_write_failed", error=str(e))

        # 2) Delta append
        row = Row(
            report_id=report.report_id,
            source_table=report.source_table,
            source_system=report.source_system,
            profiled_at=report.profiled_at,
            report_json=report_json,
        )
        df = self.spark.createDataFrame([row])

        if self.output_table:
            logger.info("writing_to_databricks_table", table=self.output_table)
            df.write.format("delta").mode("append").saveAsTable(self.output_table)
        else:
            logger.info("writing_to_local_delta", path=self.output_path)
            Path(self.output_path).mkdir(parents=True, exist_ok=True)
            df.write.format("delta").mode("append").save(self.output_path)
        
        logger.info("report_persisted_successfully", id=report.report_id)

    def get_report(self, report_id: str) -> dict:
        """
        Retrieves a specific report by ID.
        """
        # Fast path — sidecar JSON file.
        sidecar_file = self._sidecar_dir / f"{report_id}.json"
        if sidecar_file.exists():
            return json.loads(sidecar_file.read_text(encoding="utf-8"))

        # Fallback — full table scan
        try:
            if self.output_table:
                df = self.spark.table(self.output_table)
            elif Path(self.output_path).exists():
                df = self.spark.read.format("delta").load(self.output_path)
            else:
                return None
            
            res = df.filter(df.report_id == report_id).select("report_json").collect()
            if res:
                return json.loads(res[0]["report_json"])
        except Exception as e:
            logger.error("get_report_failed", error=str(e))
            
        return None
