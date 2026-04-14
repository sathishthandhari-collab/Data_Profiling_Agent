from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import Dict, List


class PatternTool:
    # Banking ID patterns.
    # Patterns that should match the full column value are anchored with ^ and $.
    # Patterns that match a distinctive prefix/suffix (e.g. ACC-, CUST-) are left unanchored.
    BANKING_PATTERNS = {
        "IBAN": r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$",   # Anchored — generic chars need full-value context.
        "ACCOUNT_NUMBER": r"ACC-\d+",
        "CUSTOMER_ID": r"CUST-\d+",
        "LOAN_ID": r"LOAN-\d+",
        "SWIFT_BIC": r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$",
    }

    @staticmethod
    def profile(df: DataFrame, total_count: int) -> Dict[str, List[str]]:
        """
        Detects specific string patterns in columns.

        Returns a mapping of column_name -> list of detected pattern types.
        A column can match multiple patterns (e.g. an IBAN column that also
        matches an ACCOUNT_NUMBER prefix), so all matches are returned.

        Args:
            df: Cached source DataFrame.
            total_count: Pre-computed row count passed from the agent state.
                         Avoids a redundant df.count() Spark action.
        """
        results: Dict[str, List[str]] = {}
        if total_count == 0:
            return results

        # Only check String columns.
        string_cols = [f.name for f in df.schema.fields if "String" in str(f.dataType)]
        if not string_cols:
            return results

        # Single-pass aggregation: non-null counts and per-pattern match counts.
        agg_exprs = []
        for c in string_cols:
            agg_exprs.append(F.count(F.col(c)).alias(f"{c}__nn"))
            for p_name, regex in PatternTool.BANKING_PATTERNS.items():
                agg_exprs.append(
                    F.sum(F.when(F.col(c).rlike(regex), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__{p_name}")
                )

        row = df.agg(*agg_exprs).collect()[0].asDict()

        for c in string_cols:
            denom = int(row.get(f"{c}__nn", 0) or 0)
            if denom == 0:
                continue
            matched: List[str] = []
            for p_name in PatternTool.BANKING_PATTERNS:
                match_count = int(row.get(f"{c}__{p_name}", 0) or 0)
                # Collect ALL patterns where the majority of non-null values match.
                # No break — a column can legitimately satisfy multiple patterns.
                if (match_count / denom) > 0.5:
                    matched.append(p_name)
            if matched:
                results[c] = matched

        return results
