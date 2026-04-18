import structlog
from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import List, Dict
from src.models.profile_report import FKHint

logger = structlog.get_logger(__name__)

class RelationTool:
    @staticmethod
    def profile(source_df: DataFrame, other_dfs: Dict[str, DataFrame]) -> List[FKHint]:
        """
        Finds potential FK relationships using:
        - Name-based candidate pruning, then
        - Approximate containment: distinct(source_col) values that appear in target_col.
        """
        hints: List[FKHint] = []
        if not other_dfs:
            return hints

        def is_id_like(col: str) -> bool:
            c = col.lower()
            return c == "id" or c.endswith("_id") or "id" in c

        def compatible_types(a: str, b: str) -> bool:
            a_num = any(t in a for t in ("Integer", "Long", "Double", "Float", "Decimal"))
            b_num = any(t in b for t in ("Integer", "Long", "Double", "Float", "Decimal"))
            a_str = "String" in a
            b_str = "String" in b
            return (a_num and b_num) or (a_str and b_str)

        source_cols = [f.name for f in source_df.schema.fields if is_id_like(f.name)]
        if not source_cols:
            return hints

        logger.info("relation_profiling_started", source_candidate_count=len(source_cols), other_tables=list(other_dfs.keys()))

        # Precompute approximate distinct counts for source candidates.
        src_card_row = source_df.agg(
            *[F.approx_count_distinct(F.col(c)).alias(c) for c in source_cols]
        ).collect()[0].asDict()
        src_cards = {c: int(src_card_row.get(c, 0) or 0) for c in source_cols}
        src_distinct: Dict[str, DataFrame] = {}

        try:
            for table_name, target_df in other_dfs.items():
                tgt_candidates = [f.name for f in target_df.schema.fields if is_id_like(f.name)]
                if not tgt_candidates:
                    continue

                tgt_card_row = target_df.agg(
                    *[F.approx_count_distinct(F.col(c)).alias(c) for c in tgt_candidates]
                ).collect()[0].asDict()
                tgt_cards = {c: int(tgt_card_row.get(c, 0) or 0) for c in tgt_candidates}
                tgt_distinct: Dict[str, DataFrame] = {}

                try:
                    for s_col in source_cols:
                        s_type = str(source_df.schema[s_col].dataType)
                        if src_cards.get(s_col, 0) == 0:
                            continue

                        for t_col in tgt_candidates:
                            t_type = str(target_df.schema[t_col].dataType)
                            if not compatible_types(s_type, t_type):
                                continue

                            # Prune by name similarity to limit join work.
                            s_norm = s_col.lower().replace("_", "")
                            t_norm = t_col.lower().replace("_", "")
                            if not (s_norm == t_norm or s_norm in t_norm or t_norm in s_norm):
                                continue

                            # Approximate containment
                            if s_col not in src_distinct:
                                src_distinct[s_col] = (
                                    source_df.select(F.col(s_col).alias("k"))
                                    .where(F.col(s_col).isNotNull())
                                    .distinct()
                                    .cache()
                                )
                                src_distinct[s_col].count()
                            if t_col not in tgt_distinct:
                                tgt_distinct[t_col] = (
                                    target_df.select(F.col(t_col).alias("k"))
                                    .where(F.col(t_col).isNotNull())
                                    .distinct()
                                    .cache()
                                )
                                tgt_distinct[t_col].count()

                            src_vals = src_distinct[s_col]
                            tgt_vals = tgt_distinct[t_col]

                            inter = (
                                src_vals.join(tgt_vals, on="k", how="leftsemi")
                                .agg(F.approx_count_distinct("k").alias("n"))
                                .collect()[0]["n"]
                            )
                            inter = int(inter or 0)
                            src_card = src_cards[s_col]
                            match_ratio = (inter / src_card) if src_card else 0.0

                            if match_ratio >= 0.90 and tgt_cards.get(t_col, 0) >= inter:
                                hints.append(
                                    FKHint(
                                        source_col=s_col,
                                        target_table=table_name,
                                        target_col=t_col,
                                        match_ratio=match_ratio,
                                    )
                                )
                finally:
                    for d in tgt_distinct.values():
                        try:
                            d.unpersist(blocking=False)
                        except Exception:
                            pass
        finally:
            for d in src_distinct.values():
                try:
                    d.unpersist(blocking=False)
                except Exception:
                    pass

        logger.info("relation_profiling_complete", hint_count=len(hints))
        return hints
