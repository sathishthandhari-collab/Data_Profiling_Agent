from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List
from src.models.profile_report import StatsProfile

class StatsTool:
    @staticmethod
    def profile(df: DataFrame) -> List[StatsProfile]:
        """
        Computes detailed stats using HLL and Spark aggregations.
        """
        total_count = df.count()
        if total_count == 0:
            return []

        cols = df.columns

        # 1) Single-pass aggregations for null counts, approximate cardinality, min/max.
        agg_exprs = []
        for c in cols:
            agg_exprs.append(F.sum(F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__nulls"))
            agg_exprs.append(F.approx_count_distinct(F.col(c)).alias(f"{c}__card"))

            dt = str(df.schema[c].dataType)
            if any(t in dt for t in ("Integer", "Long", "Double", "Float", "Decimal", "String")):
                agg_exprs.append(F.min(F.col(c)).alias(f"{c}__min"))
                agg_exprs.append(F.max(F.col(c)).alias(f"{c}__max"))

        base_row = df.agg(*agg_exprs).collect()[0].asDict()

        # 2) IQR outlier detection for numeric columns (bounds computed via one approxQuantile call).
        numeric_cols = [
            c for c in cols
            if any(t in str(df.schema[c].dataType) for t in ("Integer", "Long", "Double", "Float", "Decimal"))
        ]

        outlier_counts = {}
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
                    outlier_exprs = []
                    for c, (lb, ub) in bounds.items():
                        outlier_exprs.append(
                            F.sum(
                                F.when(
                                    (F.col(c) < F.lit(lb)) | (F.col(c) > F.lit(ub)),
                                    F.lit(1),
                                ).otherwise(F.lit(0))
                            ).alias(f"{c}__outliers")
                        )
                    outlier_row = df.agg(*outlier_exprs).collect()[0].asDict()
                    for c in bounds:
                        outlier_counts[c] = int(outlier_row.get(f"{c}__outliers", 0) or 0)
            except Exception:
                # If quantiles fail (e.g. all-null numeric columns), skip outlier detection.
                outlier_counts = {}

        # 3) Assemble typed profiles.
        out: List[StatsProfile] = []
        for c in cols:
            nulls = int(base_row.get(f"{c}__nulls", 0) or 0)
            card = int(base_row.get(f"{c}__card", 0) or 0)
            min_v = base_row.get(f"{c}__min", None)
            max_v = base_row.get(f"{c}__max", None)

            out.append(
                StatsProfile(
                    column=c,
                    null_pct=(nulls / total_count),
                    cardinality_est=card,
                    min_val=str(min_v) if min_v is not None else None,
                    max_val=str(max_v) if max_v is not None else None,
                    has_outliers=(outlier_counts.get(c, 0) > 0),
                )
            )

        return out
