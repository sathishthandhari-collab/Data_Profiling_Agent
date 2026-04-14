from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List
from src.models.profile_report import ColumnSchema

class SchemaTool:
    @staticmethod
    def profile(df: DataFrame) -> List[ColumnSchema]:
        """
        Analyzes the DataFrame schema and identifies PK candidates.
        """
        total_count = df.count()
        if total_count == 0:
            return []

        cols = df.columns

        # Single-pass null counts + approximate distinct counts (cheap enough and avoids per-column actions).
        null_exprs = [
            F.sum(F.when(F.col(c).isNull(), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__nulls")
            for c in cols
        ]
        approx_exprs = [F.approx_count_distinct(F.col(c)).alias(f"{c}__adist") for c in cols]
        row = df.agg(*null_exprs, *approx_exprs).collect()[0].asDict()

        schemas: List[ColumnSchema] = []
        # Only run exact distinct for the handful of likely PKs to avoid a job per column.
        maybe_pk_cols = []
        for field in df.schema:
            col = field.name
            nulls = int(row.get(f"{col}__nulls", 0) or 0)
            approx_distinct = int(row.get(f"{col}__adist", 0) or 0)
            if nulls == 0 and approx_distinct == total_count:
                maybe_pk_cols.append(col)

        exact_distinct = {}
        for col in maybe_pk_cols:
            exact_distinct[col] = df.select(F.col(col)).distinct().count()

        for field in df.schema:
            col_name = field.name
            spark_type = str(field.dataType)
            nullable = field.nullable
            nulls = int(row.get(f"{col_name}__nulls", 0) or 0)
            approx_distinct = int(row.get(f"{col_name}__adist", 0) or 0)

            unique_count = exact_distinct.get(col_name, approx_distinct)
            uniqueness_ratio = unique_count / total_count if total_count else 0.0

            # PK heuristic: no nulls observed and truly unique (verify exact for candidates).
            is_pk = (nulls == 0) and (unique_count == total_count)

            schemas.append(
                ColumnSchema(
                    name=col_name,
                    spark_type=spark_type,
                    nullable=nullable,
                    is_pk_candidate=is_pk,
                    uniqueness_ratio=uniqueness_ratio,
                )
            )

        return schemas
