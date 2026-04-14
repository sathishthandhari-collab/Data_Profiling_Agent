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

        # Sidecar directory: one JSON file per report_id for O(1) retrieval.
        # Avoids the full Delta table scan that was previously triggered on every GET.
        self._sidecar_dir = Path(self.output_path) / "_reports"

    def write_report(self, report: ProfileReport):
        """
        Serializes the ProfileReport to JSON and saves it to a Delta table.

        Also writes a sidecar JSON file keyed by report_id so that
        get_report() can retrieve any report in O(1) without scanning Delta.
        """
        print(f"💾 Saving profile report for {report.source_table} to Delta...")

        report_json = report.model_dump_json()

        # 1) Sidecar JSON — O(1) lookup for GET /report/{id}.
        self._sidecar_dir.mkdir(parents=True, exist_ok=True)
        (self._sidecar_dir / f"{report.report_id}.json").write_text(report_json, encoding="utf-8")

        # 2) Delta append — supports analytics, listing, history, and time travel.
        row = Row(
            report_id=report.report_id,
            source_table=report.source_table,
            source_system=report.source_system,
            profiled_at=report.profiled_at,
            report_json=report_json,
        )
        df = self.spark.createDataFrame([row])
        Path(self.output_path).mkdir(parents=True, exist_ok=True)
        df.write.format("delta").mode("append").save(self.output_path)
        print(f"   ✅ Report persisted at {self.output_path}")

    def get_report(self, report_id: str) -> dict:
        """
        Retrieves a specific report by ID.

        Fast path: reads from the sidecar JSON file (O(1), no Spark job).
        Fallback: scans the Delta table (for reports written before the sidecar
        was introduced, or if the sidecar file was manually removed).
        """
        # Fast path — sidecar JSON file.
        sidecar_file = self._sidecar_dir / f"{report_id}.json"
        if sidecar_file.exists():
            return json.loads(sidecar_file.read_text(encoding="utf-8"))

        # Fallback — full Delta scan (legacy behaviour).
        if not Path(self.output_path).exists():
            return None
        df = self.spark.read.format("delta").load(self.output_path)
        res = df.filter(df.report_id == report_id).select("report_json").collect()
        if res:
            return json.loads(res[0]["report_json"])
        return None
