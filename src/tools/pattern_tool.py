import os
import yaml
import structlog
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import Dict, List, Any

logger = structlog.get_logger(__name__)

class PatternTool:
    # Layer 1: Universal banking patterns (always active)
    UNIVERSAL_PATTERNS = {
        "IBAN": r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$",
        "SWIFT_BIC": r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$",
        "ISO_8601": r"^\d{4}-\d{2}-\d{2}",
        "ISO_4217": r"^[A-Z]{3}$",
        "EMAIL": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    }

    def __init__(self, config_path: str = "config/patterns.yaml"):
        self.custom_patterns = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    self.custom_patterns = config.get("custom_patterns", {})
                    logger.info("loaded_custom_patterns", count=len(self.custom_patterns))
            except Exception as e:
                logger.error("failed_to_load_patterns_config", error=str(e))

    def profile(self, df: DataFrame, total_count: int) -> Dict[str, Any]:
        """
        3-layer hybrid pattern detection:
        1. Universal banking patterns (Code)
        2. Source-system patterns (Config)
        3. Data-driven heuristics (Discovery)
        """
        if total_count == 0:
            return {}

        string_cols = [f.name for f in df.schema.fields if "String" in str(f.dataType)]
        if not string_cols:
            return {}

        all_patterns = {**self.UNIVERSAL_PATTERNS, **self.custom_patterns}
        
        # Aggregation expressions for Layers 1 & 2
        agg_exprs = []
        for c in string_cols:
            agg_exprs.append(F.count(F.col(c)).alias(f"{c}__nn"))
            for p_name, regex in all_patterns.items():
                agg_exprs.append(
                    F.sum(F.when(F.col(c).rlike(regex), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__{p_name}")
                )
            
            # Layer 3: Heuristics - Distinct count for cardinality
            agg_exprs.append(F.approx_count_distinct(F.col(c)).alias(f"{c}__adist"))

        try:
            row = df.agg(*agg_exprs).collect()[0].asDict()
        except Exception as e:
            logger.error("pattern_agg_failed", error=str(e))
            return {}

        results = {}
        for c in string_cols:
            denom = int(row.get(f"{c}__nn", 0) or 0)
            if denom == 0:
                continue

            matched_patterns = []
            for p_name in all_patterns:
                match_count = int(row.get(f"{c}__{p_name}", 0) or 0)
                if (match_count / denom) > 0.5:
                    matched_patterns.append(p_name)

            # Layer 3: Heuristics
            heuristics = []
            col_lower = c.lower()
            
            # Column name hints
            if col_lower.endswith(("_id", "_pk", "_key")):
                heuristics.append("LIKELY_KEY")
            if col_lower.endswith(("_date", "_dt", "_timestamp")):
                heuristics.append("LIKELY_TEMPORAL")
            if col_lower.endswith(("_amt", "_amount", "_bal", "_balance")):
                heuristics.append("LIKELY_MEASURE")
            
            # Data-driven hints
            approx_dist = int(row.get(f"{c}__adist", 0) or 0)
            uniqueness = approx_dist / total_count
            if uniqueness > 0.95 and denom == total_count:
                heuristics.append("HIGH_UNIQUENESS_CANDIDATE")
            elif approx_dist < 50 and approx_dist / denom < 0.1:
                heuristics.append("LOW_CARDINALITY_CATEGORICAL")

            if matched_patterns or heuristics:
                results[c] = {
                    "patterns": matched_patterns,
                    "heuristics": heuristics,
                    "uniqueness_score": uniqueness
                }

        return results
