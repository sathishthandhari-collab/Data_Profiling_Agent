import re
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List, Dict

class PatternTool:
    # Banking ID Patterns
    BANKING_PATTERNS = {
        "IBAN": r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}",
        "ACCOUNT_NUMBER": r"ACC-\d+",
        "CUSTOMER_ID": r"CUST-\d+",
        "LOAN_ID": r"LOAN-\d+",
        "SWIFT_BIC": r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$"
    }

    @staticmethod
    def profile(df: DataFrame) -> Dict[str, str]:
        """
        Detects specific string patterns in columns.
        Returns a mapping of column_name -> detected_pattern_type.
        """
        results = {}
        total_count = df.count()
        if total_count == 0:
            return results

        # Only check String columns
        string_cols = [f.name for f in df.schema.fields if "String" in str(f.dataType)]

        if not string_cols:
            return results

        # Compute non-null counts and match counts in a single aggregation.
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
            for p_name in PatternTool.BANKING_PATTERNS.keys():
                match_count = int(row.get(f"{c}__{p_name}", 0) or 0)
                if (match_count / denom) > 0.5:  # Majority match among non-nulls
                    results[c] = p_name
                    break
        
        return results
