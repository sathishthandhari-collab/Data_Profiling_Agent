from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List
from src.models.profile_report import ColumnSchema


class SchemaTool:
    @staticmethod
    def profile(df: DataFrame, total_count: int) -> List[ColumnSchema]:
        """
        Analyzes the DataFrame schema and identifies PK candidates.

        Args:
            df: Cached source DataFrame.
            total_count: Pre-computed row count passed from the agent state.
                         Avoids a redundant df.count() Spark action.
        """
        if total_count == 0:
            return []

        cols = df.columns

        # Single-pass: null counts + approximate distinct counts.
        null_exprs = [
            F.sum(F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__nulls")
            for c in cols
        ]
        approx_exprs = [F.approx_count_distinct(F.col(c)).alias(f"{c}__adist") for c in cols]
        row = df.agg(*null_exprs, *approx_exprs).collect()[0].asDict()

        # Identify candidate PK columns for exact verification.
        maybe_pk_cols = [
            field.name
            for field in df.schema
            if (
                int(row.get(f"{field.name}__nulls", 0) or 0) == 0
                and int(row.get(f"{field.name}__adist", 0) or 0) == total_count
            )
        ]

        # Batch all exact distinct counts into ONE Spark job (was N sequential jobs).
        exact_distinct: dict = {}
        if maybe_pk_cols:
            exact_agg_row = (
                df.agg(*[F.countDistinct(F.col(c)).alias(c) for c in maybe_pk_cols])
                .collect()[0]
                .asDict()
            )
            exact_distinct = {c: int(exact_agg_row.get(c, 0) or 0) for c in maybe_pk_cols}

        schemas: List[ColumnSchema] = []
        for field in df.schema:
            col_name = field.name
            nulls = int(row.get(f"{col_name}__nulls", 0) or 0)
            approx_distinct = int(row.get(f"{col_name}__adist", 0) or 0)

            # Use verified exact count for PK candidates; approx elsewhere.
            unique_count = exact_distinct.get(col_name, approx_distinct)
            uniqueness_ratio = unique_count / total_count if total_count else 0.0

            # PK heuristic: no nulls observed AND truly unique (exact-count verified).
            is_pk = (nulls == 0) and (unique_count == total_count)

            schemas.append(
                ColumnSchema(
                    name=col_name,
                    spark_type=str(field.dataType),
                    nullable=field.nullable,
                    is_pk_candidate=is_pk,
                    uniqueness_ratio=uniqueness_ratio,
                )
            )

        return schemas
