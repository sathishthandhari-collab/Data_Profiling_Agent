import re
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List
from src.models.profile_report import PIIProfile


# Matches column names that are strongly indicative of a *person's* name field.
# Allows: name, first_name, last_name, full_name, given_name, customer_name, etc.
# Rejects: product_name, country_name, file_name, username, column_name, etc.
_PERSON_NAME_COL = re.compile(
    r"^(?:(?:first|last|full|given|middle|sur|family|"
    r"customer|person|employee|client|owner|contact)_)?name$"
)


class PIITool:
    # Common PII regex patterns.
    PATTERNS = {
        "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "SSN": r"\d{3}-\d{2}-\d{4}",
        "PHONE": r"(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}",
        # Add more patterns as needed.
    }

    @staticmethod
    def profile(df: DataFrame, total_count: int) -> List[PIIProfile]:
        """
        Detects PII using regex patterns and column-name heuristics.

        Args:
            df: Cached source DataFrame.
            total_count: Pre-computed row count passed from the agent state.
                         Avoids a redundant df.count() Spark action.
        """
        pii_profiles = []
        if total_count == 0:
            return pii_profiles

        # Only check String columns for regex-based PII detection.
        string_cols = [f.name for f in df.schema.fields if "String" in str(f.dataType)]
        if not string_cols:
            return pii_profiles

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

            for p_type in PIITool.PATTERNS:
                match_count = int(row.get(f"{col}__{p_type}", 0) or 0)
                confidence = (match_count / denom) if denom else 0.0

                if confidence > 0.1:  # Threshold for detection.
                    is_pii = True
                    if confidence > max_confidence:
                        pii_type = p_type
                        max_confidence = confidence

            # Column-name heuristic: only flag columns whose name specifically
            # denotes a person's name (e.g. name, first_name, last_name).
            # Avoids false positives on product_name, country_name, file_name, etc.
            if not is_pii and _PERSON_NAME_COL.match(col.lower()):
                is_pii = True
                pii_type = "NAME"
                max_confidence = 0.75  # Moderate confidence — heuristic, not data-driven.

            pii_profiles.append(
                PIIProfile(
                    column=col,
                    is_pii=is_pii,
                    pii_type=pii_type,
                    confidence=max_confidence,
                )
            )

        return pii_profiles
