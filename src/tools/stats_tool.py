import structlog
from decimal import Decimal
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List, Optional, Union, Any
from src.models.profile_report import StatsProfile

logger = structlog.get_logger(__name__)

def _coerce_val(v) -> Optional[Union[int, float, str]]:
    """
    Coerce a Spark aggregate result to a JSON-serialisable native Python type.
    Handles Decimal (returned by Spark for DecimalType columns) → float.
    """
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, Decimal):
        return float(v)
    # Fallback for any other Spark type (e.g. datetime — not expected here but safe).
    return str(v)


class StatsTool:
    @staticmethod
    def profile(df: DataFrame, total_count: int) -> List[StatsProfile]:
        """
        Computes detailed column statistics using Spark aggregations and HLL.

        Args:
            df: Cached source DataFrame.
            total_count: Pre-computed row count passed from the agent state.
                         Avoids a redundant df.count() Spark action.
        """
        if total_count == 0:
            return []

        cols = df.columns
        logger.info("stats_profiling_started", column_count=len(cols))

        # 1) Single-pass aggregations: null counts, cardinality, min/max, mean, stddev.
        agg_exprs = []
        for c in cols:
            dt = str(df.schema[c].dataType)
            agg_exprs.append(
                F.sum(F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__nulls")
            )
            agg_exprs.append(F.approx_count_distinct(F.col(c)).alias(f"{c}__card"))

            if any(t in dt for t in ("Integer", "Long", "Double", "Float", "Decimal", "String")):
                agg_exprs.append(F.min(F.col(c)).alias(f"{c}__min"))
                agg_exprs.append(F.max(F.col(c)).alias(f"{c}__max"))

            # Mean and stddev only make sense for numeric types.
            if any(t in dt for t in ("Integer", "Long", "Double", "Float", "Decimal")):
                agg_exprs.append(F.mean(F.col(c)).alias(f"{c}__mean"))
                agg_exprs.append(F.stddev(F.col(c)).alias(f"{c}__stddev"))

        try:
            base_row = df.agg(*agg_exprs).collect()[0].asDict()
        except Exception as e:
            logger.error("stats_agg_failed", error=str(e))
            return []

        # 2) IQR outlier detection for numeric columns (single approxQuantile call).
        numeric_cols = [
            c for c in cols
            if any(t in str(df.schema[c].dataType) for t in ("Integer", "Long", "Double", "Float", "Decimal"))
        ]

        outlier_counts: dict = {}
        if numeric_cols:
            try:
                qs = df.approxQuantile(numeric_cols, [0.25, 0.75], 0.05)
                bounds = {}
                for c, q in zip(numeric_cols, qs):
                    if not q or len(q) < 2:
                        continue
                    q1, q3 = q[0], q[1]
                    iqr = q3 - q1
                    bounds[c] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)

                if bounds:
                    outlier_exprs = [
                        F.sum(
                            F.when(
                                (F.col(c) < F.lit(lb)) | (F.col(c) > F.lit(ub)),
                                F.lit(1),
                            ).otherwise(F.lit(0))
                        ).alias(f"{c}__outliers")
                        for c, (lb, ub) in bounds.items()
                    ]
                    outlier_row = df.agg(*outlier_exprs).collect()[0].asDict()
                    for c in bounds:
                        outlier_counts[c] = int(outlier_row.get(f"{c}__outliers", 0) or 0)
            except Exception as e:
                # Quantiles can fail on all-null columns — skip outlier detection gracefully.
                logger.warning("outlier_detection_skipped", error=str(e))
                outlier_counts = {}

        # 3) Assemble typed profiles with native-typed min/max values.
        out: List[StatsProfile] = []
        for c in cols:
            nulls = int(base_row.get(f"{c}__nulls", 0) or 0)
            card = int(base_row.get(f"{c}__card", 0) or 0)
            mean_raw = base_row.get(f"{c}__mean", None)
            sdv_raw = base_row.get(f"{c}__stddev", None)

            out.append(
                StatsProfile(
                    column=c,
                    null_pct=(nulls / total_count),
                    cardinality_est=card,
                    min_val=_coerce_val(base_row.get(f"{c}__min", None)),
                    max_val=_coerce_val(base_row.get(f"{c}__max", None)),
                    mean_val=float(mean_raw) if mean_raw is not None else None,
                    stddev_val=float(sdv_raw) if sdv_raw is not None else None,
                    has_outliers=(outlier_counts.get(c, 0) > 0),
                )
            )

        logger.info("stats_profiling_complete", column_count=len(out))
        return out
