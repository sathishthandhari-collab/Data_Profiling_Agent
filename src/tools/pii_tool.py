from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List
from src.models.profile_report import PIIProfile

class PIITool:
    # Common PII Patterns
    PATTERNS = {
        "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "SSN": r"\d{3}-\d{2}-\d{4}",
        "PHONE": r"(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}",
        # Add more patterns as needed
    }

    @staticmethod
    def profile(df: DataFrame) -> List[PIIProfile]:
        """
        Detects PII using regex patterns and returns a profile per column.
        """
        pii_profiles = []
        total_count = df.count()
        if total_count == 0:
            return []

        # We only check String columns for PII
        string_cols = [f.name for f in df.schema.fields if "String" in str(f.dataType)]
        if not string_cols:
            return []

        # Single-pass aggregation: non-null counts and pattern match counts.
        agg_exprs = []
        for c in string_cols:
            agg_exprs.append(F.count(F.col(c)).alias(f"{c}__nn"))
            for p_type, regex in PIITool.PATTERNS.items():
                agg_exprs.append(
                    F.sum(F.when(F.col(c).rlike(regex), F.lit(1)).otherwise(F.lit(0))).alias(f"{c}__{p_type}")
                )
        row = df.agg(*agg_exprs).collect()[0].asDict()
        
        for col in string_cols:
            is_pii = False
            pii_type = None
            max_confidence = 0.0
            denom = int(row.get(f"{col}__nn", 0) or 0)

            for p_type, regex in PIITool.PATTERNS.items():
                match_count = int(row.get(f"{col}__{p_type}", 0) or 0)
                confidence = (match_count / denom) if denom else 0.0
                
                if confidence > 0.1:  # Threshold for detection
                    is_pii = True
                    if confidence > max_confidence:
                        pii_type = p_type
                        max_confidence = confidence

            # Special case for "name" in column name (Heuristic)
            if not is_pii and "name" in col.lower():
                is_pii = True
                pii_type = "NAME"
                max_confidence = 0.8  # High heuristic confidence

            pii_profiles.append(PIIProfile(
                column=col,
                is_pii=is_pii,
                pii_type=pii_type,
                confidence=max_confidence
            ))

        return pii_profiles
