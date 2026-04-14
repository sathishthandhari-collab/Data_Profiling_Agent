import json
import logging
import os
from typing import Any, Dict, List
from pathlib import Path
from langgraph.graph import StateGraph, END
from litellm import completion
from dotenv import load_dotenv

from src.agent.state import AgentState
from src.reader.data_reader import DataReader
from src.tools.schema_tool import SchemaTool
from src.tools.stats_tool import StatsTool
from src.tools.pii_tool import PIITool
from src.tools.relation_tool import RelationTool
from src.tools.pattern_tool import PatternTool
from src.agent.prompts.system_prompt import SYSTEM_PROMPT
from src.agent.prompts.interpretation_prompt import INTERPRETATION_PROMPT
from src.models.profile_report import ProfileReport, LLMInterpretation

load_dotenv()

logger = logging.getLogger(__name__)


def _esc(s: str) -> str:
    """
    Escape curly braces in a string so Python's str.format() treats them as
    literals rather than format-field delimiters.  Required when injecting
    JSON payloads (which contain { and }) into an str.format() template.
    """
    return s.replace("{", "{{").replace("}", "}}")


class ProfilingAgent:
    def __init__(self, model_name: str = "gemini/gemini-1.5-pro"):
        self.model_name = model_name
        self.reader = DataReader()
        self.workflow = self._build_graph()

    def _data_root(self) -> Path:
        return Path(os.getenv("DATA_PATH", "data"))

    def _build_graph(self):
        graph = StateGraph(AgentState)

        # Define Nodes
        graph.add_node("reader", self.node_reader)
        graph.add_node("profiler", self.node_profiler)
        graph.add_node("summarizer", self.node_summarizer)
        graph.add_node("interpreter", self.node_interpreter)

        # Define Edges
        graph.set_entry_point("reader")
        graph.add_edge("reader", "profiler")
        graph.add_edge("profiler", "summarizer")
        graph.add_edge("summarizer", "interpreter")
        graph.add_edge("interpreter", END)

        return graph.compile()

    def node_reader(self, state: AgentState):
        df = self.reader.load_data(state["source_config"]).cache()
        row_count = df.count()  # Materialize cache once; tools reuse this value.
        return {"df": df, "df_rows_count": row_count}

    def node_profiler(self, state: AgentState):
        df = state["df"]
        row_count = state["df_rows_count"]
        # Normalise to lowercase for case-insensitive self-exclusion below.
        current_table = state["source_config"].table.lower()

        # Load other DataFrames for Relation Discovery.
        other_dfs: Dict[str, Any] = {}
        delta_base = self._data_root() / "delta"
        if delta_base.exists():
            for table_dir in delta_base.iterdir():
                if not table_dir.is_dir():
                    continue
                # Case-insensitive comparison prevents self-referential FK hints
                # when the directory name differs only by case from current_table.
                if table_dir.name.lower() in {current_table, "profiling_reports"}:
                    continue
                try:
                    other_dfs[table_dir.name] = self.reader.spark.read.format("delta").load(str(table_dir))
                except Exception:
                    # Relation discovery is best-effort; don't fail the whole run.
                    continue

        # Pass row_count to every tool — eliminates 4 redundant df.count() calls.
        return {
            "column_schemas": SchemaTool.profile(df, row_count),
            "stats_profiles": StatsTool.profile(df, row_count),
            "pii_profiles": PIITool.profile(df, row_count),
            "detected_patterns": PatternTool.profile(df, row_count),
            "fk_hints": RelationTool.profile(df, other_dfs),
        }

    def node_summarizer(self, state: AgentState):
        """Summarizes/ranks columns to keep the LLM context bounded."""
        stats = state["stats_profiles"]
        if not stats:
            return {"summarized_stats": []}

        pii_cols = {p.column for p in state.get("pii_profiles", []) if p.is_pii}
        pattern_cols = set((state.get("detected_patterns") or {}).keys())
        pk_cols = {c.name for c in state.get("column_schemas", []) if c.is_pk_candidate}

        if len(stats) <= 50:
            # Small tables: pass full stats through (more useful than truncation).
            return {"summarized_stats": [s.model_dump() for s in stats]}

        interesting_cols: set = set()
        interesting_cols |= pii_cols
        interesting_cols |= pattern_cols
        interesting_cols |= pk_cols
        for s in stats:
            if s.null_pct >= 0.10 or s.has_outliers:
                interesting_cols.add(s.column)

        scored = sorted(
            stats,
            key=lambda x: (
                (2.0 if x.column in pii_cols else 0.0)
                + (1.5 if x.column in pk_cols else 0.0)
                + (1.0 if x.column in pattern_cols else 0.0)
                + x.null_pct
                + (1.0 if x.has_outliers else 0.0)
            ),
            reverse=True,
        )

        max_items = 30
        selected = []
        seen: set = set()
        # Ensure flagged columns are included first.
        for s in scored:
            if s.column in interesting_cols and s.column not in seen:
                selected.append(s)
                seen.add(s.column)
                if len(selected) >= max_items:
                    break
        # Fill remaining slots with top-scored columns.
        if len(selected) < max_items:
            for s in scored:
                if s.column not in seen:
                    selected.append(s)
                    seen.add(s.column)
                    if len(selected) >= max_items:
                        break

        return {"summarized_stats": [s.model_dump() for s in selected]}

    def _fallback_interpretation(self, state: AgentState) -> LLMInterpretation:
        cfg = state["source_config"]
        pk_cols = [c.name for c in state.get("column_schemas", []) if c.is_pk_candidate]
        if not pk_cols:
            pk_cols = [c.name for c in state.get("column_schemas", []) if "id" in c.name.lower()]

        bk_candidates = [
            {"column": c, "confidence": 0.65, "reasoning": "Heuristic: unique/non-null or ID-like column."}
            for c in pk_cols[:3]
        ]

        pii = [p for p in state.get("pii_profiles", []) if p.is_pii]
        pii_summary = []
        for p in pii[:10]:
            if p.pii_type:
                pii_summary.append(f"{p.column}: detected {p.pii_type} (confidence {p.confidence:.2f}).")
            else:
                pii_summary.append(f"{p.column}: detected PII (confidence {p.confidence:.2f}).")

        dq_flags = []
        for s in state.get("stats_profiles", []):
            if s.null_pct >= 0.20:
                dq_flags.append(f"{s.column} has high null rate ({s.null_pct:.0%}).")
            if s.has_outliers:
                dq_flags.append(f"{s.column} shows outliers (IQR heuristic).")
            if len(dq_flags) >= 10:
                break

        suggested = cfg.name or cfg.table
        suggested_entity_name = suggested.replace("_", " ").title()
        return LLMInterpretation(
            suggested_entity_name=suggested_entity_name,
            bk_candidates=bk_candidates,
            pii_summary=pii_summary,
            dq_flags=dq_flags,
            confidence=0.25,
        )

    def node_interpreter(self, state: AgentState):
        # Carry forward any errors accumulated by earlier nodes.
        errors: List[str] = list(state.get("errors") or [])

        # Serialize all list/dict inputs as compact JSON before prompt injection.
        # Rationale: str.format() would call repr() on raw lists, producing noisy
        # Python syntax.  JSON is both cleaner for the LLM and avoids str.format()
        # misinterpreting JSON braces as format-field delimiters (handled by _esc).
        pk_json      = _esc(json.dumps([s.name for s in state["column_schemas"] if s.is_pk_candidate], default=str))
        stats_json   = _esc(json.dumps(state["summarized_stats"], default=str, indent=2))
        pii_json     = _esc(json.dumps([p.column for p in state["pii_profiles"] if p.is_pii], default=str))
        patterns_json = _esc(json.dumps(state["detected_patterns"], default=str, indent=2))
        fk_json      = _esc(json.dumps([h.model_dump() for h in state["fk_hints"]], default=str, indent=2))

        prompt = INTERPRETATION_PROMPT.format(
            table_name=state["source_config"].name,
            source_system=state["source_config"].source_system,
            row_count=state["df_rows_count"],
            pk_candidates=pk_json,
            stats_summary=stats_json,
            pii_findings=pii_json,
            pattern_detections=patterns_json,
            fk_hints=fk_json,
        )

        disable_llm = os.getenv("DISABLE_LLM", "").strip().lower() in {"1", "true", "yes"}
        interpretation: LLMInterpretation

        if disable_llm:
            interpretation = self._fallback_interpretation(state)
        else:
            try:
                response = completion(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                try:
                    interpretation_dict = json.loads(content)
                except Exception:
                    # Best-effort extraction if the model wraps JSON in text.
                    import re
                    m = re.search(r"\{.*\}", content, flags=re.DOTALL)
                    if not m:
                        raise
                    interpretation_dict = json.loads(m.group(0))

                interpretation = LLMInterpretation(**interpretation_dict)

            except Exception as e:
                # Log the failure with full context so it's diagnosable, then
                # fall back to heuristics so the agent always returns a report.
                logger.warning(
                    "LLM interpretation failed (%s: %s) — using heuristic fallback.",
                    type(e).__name__, e,
                )
                errors.append(f"LLM interpretation failed: {type(e).__name__}: {e}")
                interpretation = self._fallback_interpretation(state)

        # Final Assembly — always runs regardless of LLM success/failure.
        report = ProfileReport(
            source_table=state["source_config"].name,
            source_system=state["source_config"].source_system,
            row_count=state["df_rows_count"],
            columns=state["column_schemas"],
            stats=state["stats_profiles"],
            pii_info=state["pii_profiles"],
            fk_hints=state["fk_hints"],
            interpretation=interpretation,
        )

        # Release cached data for this run to avoid unbounded executor memory growth.
        try:
            state["df"].unpersist(blocking=False)
        except Exception:
            pass

        return {"errors": errors, "interpretation": interpretation, "final_report": report}

    def run(self, source_config):
        initial_state = {
            "source_config": source_config,
            "errors": [],
        }
        return self.workflow.invoke(initial_state)
