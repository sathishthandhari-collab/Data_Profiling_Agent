import json
import os
import structlog
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
from langgraph.graph import StateGraph, END
from litellm import completion
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

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
from src.models.source_config import SourceConfig

load_dotenv()

logger = structlog.get_logger(__name__)

def _esc(s: str) -> str:
    return s.replace("{", "{{").replace("}", "}}")

class ProfilingAgent:
    def __init__(self, model_name: str = "gemini/gemini-2.5-flash"):
        self.model_name = model_name
        self.reader = DataReader()
        self.pattern_tool = PatternTool()
        self.workflow = self._build_graph()

    def _data_root(self) -> Path:
        return Path(os.getenv("DATA_PATH", "data"))

    def _build_graph(self):
        graph = StateGraph(AgentState)

        graph.add_node("reader", self.node_reader)
        graph.add_node("profiler", self.node_profiler)
        graph.add_node("summarizer", self.node_summarizer)
        graph.add_node("interpreter", self.node_interpreter)

        graph.set_entry_point("reader")
        graph.add_edge("reader", "profiler")
        graph.add_edge("profiler", "summarizer")
        graph.add_edge("summarizer", "interpreter")
        graph.add_edge("interpreter", END)

        return graph.compile()

    def node_reader(self, state: AgentState):
        logger.info("node_reader_started", table=state["source_config"].table)
        df = self.reader.load_data(state["source_config"])
        
        row_count = df.count()
        
        # Guard: if row_count > 10M, sample to 1M
        if row_count > 10_000_000:
            fraction = 1_000_000 / row_count
            logger.warning("large_table_sampling_active", row_count=row_count, sample_fraction=fraction)
            df = df.sample(fraction=fraction)
        
        df = df.cache()
        # Trigger cache materialization
        df.count()
        
        return {"df": df, "df_rows_count": row_count}

    def node_profiler(self, state: AgentState):
        df = state["df"]
        row_count = state["df_rows_count"]
        current_table = state["source_config"].table.lower()

        logger.info("node_profiler_started", table=current_table)

        # Load other DataFrames for Relation Discovery
        other_dfs: Dict[str, Any] = {}
        delta_base = self._data_root() / "delta"
        if delta_base.exists():
            for table_dir in delta_base.iterdir():
                if not table_dir.is_dir():
                    continue
                if table_dir.name.lower() in {current_table, "profiling_reports"}:
                    continue
                try:
                    other_dfs[table_dir.name] = self.reader.spark.read.format("delta").load(str(table_dir))
                except Exception:
                    continue

        errors = list(state.get("errors") or [])
        
        # Tools are independent, try/except each
        try:
            column_schemas = SchemaTool.profile(df, row_count)
        except Exception as e:
            logger.error("schema_tool_failed", error=str(e))
            errors.append(f"SchemaTool failed: {str(e)}")
            column_schemas = []

        try:
            stats_profiles = StatsTool.profile(df, row_count)
        except Exception as e:
            logger.error("stats_tool_failed", error=str(e))
            errors.append(f"StatsTool failed: {str(e)}")
            stats_profiles = []

        try:
            pii_profiles = PIITool.profile(df, row_count)
        except Exception as e:
            logger.error("pii_tool_failed", error=str(e))
            errors.append(f"PIITool failed: {str(e)}")
            pii_profiles = []

        try:
            detected_patterns = self.pattern_tool.profile(df, row_count)
        except Exception as e:
            logger.error("pattern_tool_failed", error=str(e))
            errors.append(f"PatternTool failed: {str(e)}")
            detected_patterns = {}

        try:
            fk_hints = RelationTool.profile(df, other_dfs)
        except Exception as e:
            logger.error("relation_tool_failed", error=str(e))
            errors.append(f"RelationTool failed: {str(e)}")
            fk_hints = []

        return {
            "column_schemas": column_schemas,
            "stats_profiles": stats_profiles,
            "pii_profiles": pii_profiles,
            "detected_patterns": detected_patterns,
            "fk_hints": fk_hints,
            "errors": errors
        }

    def node_summarizer(self, state: AgentState):
        stats = state["stats_profiles"]
        if not stats:
            return {"summarized_stats": []}

        pii_cols = {p.column for p in state.get("pii_profiles", []) if p.is_pii}
        pattern_cols = set((state.get("detected_patterns") or {}).keys())
        pk_cols = {c.name for c in state.get("column_schemas", []) if c.is_pk_candidate}

        if len(stats) <= 50:
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
        for s in scored:
            if s.column in interesting_cols and s.column not in seen:
                selected.append(s)
                seen.add(s.column)
                if len(selected) >= max_items:
                    break
        
        if len(selected) < max_items:
            for s in scored:
                if s.column not in seen:
                    selected.append(s)
                    seen.add(s.column)
                    if len(selected) >= max_items:
                        break

        return {"summarized_stats": [s.model_dump() for s in selected]}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_llm(self, prompt: str):
        response = completion(
            model=self.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

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
            pii_summary.append(f"{p.column}: detected {p.pii_type or 'PII'} (confidence {p.confidence:.2f}).")

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
        errors = list(state.get("errors") or [])
        
        pk_json      = _esc(json.dumps([s.name for s in state["column_schemas"] if s.is_pk_candidate], default=str))
        stats_json   = _esc(json.dumps(state["summarized_stats"], default=str, indent=2))
        pii_json     = _esc(json.dumps([p.column for p in state["pii_profiles"] if p.is_pii], default=str))
        patterns_json = _esc(json.dumps(state["detected_patterns"], default=str, indent=2))
        fk_json      = _esc(json.dumps([h.model_dump() for h in state["fk_hints"]], default=str, indent=2))

        prompt = INTERPRETATION_PROMPT.format(
            table_name=state["source_config"].name or state["source_config"].table,
            source_system=state["source_config"].source_system,
            row_count=state["df_rows_count"],
            pk_candidates=pk_json,
            stats_summary=stats_json,
            pii_findings=pii_json,
            pattern_detections=patterns_json,
            fk_hints=fk_json,
        )

        disable_llm = os.getenv("DISABLE_LLM", "").strip().lower() in {"1", "true", "yes"}
        interpretation: Optional[LLMInterpretation] = None

        if disable_llm:
            interpretation = self._fallback_interpretation(state)
        else:
            try:
                content = self._call_llm(prompt)
                try:
                    interpretation_dict = json.loads(content)
                except Exception:
                    import re
                    m = re.search(r"\{.*\}", content, flags=re.DOTALL)
                    if not m: raise
                    interpretation_dict = json.loads(m.group(0))

                interpretation = LLMInterpretation(**interpretation_dict)
            except Exception as e:
                logger.warning("llm_interpretation_failed", error=str(e))
                errors.append(f"LLM interpretation failed: {str(e)}")
                interpretation = self._fallback_interpretation(state)

        report = ProfileReport(
            source_table=state["source_config"].table,
            source_system=state["source_config"].source_system,
            row_count=state.get("original_row_count", state["df_rows_count"]),
            columns=state["column_schemas"],
            stats=state["stats_profiles"],
            pii_info=state["pii_profiles"],
            fk_hints=state["fk_hints"],
            interpretation=interpretation,
        )

        try:
            state["df"].unpersist(blocking=False)
        except Exception:
            pass

        return {"errors": errors, "interpretation": interpretation, "final_report": report}

    def run(self, source_config: SourceConfig):
        start_time = time.time()
        logger.info("agent_run_started", table=source_config.table)
        
        initial_state = {
            "source_config": source_config,
            "errors": [],
        }
        result = self.workflow.invoke(initial_state)
        
        duration = time.time() - start_time
        logger.info("agent_run_complete", table=source_config.table, duration=duration)
        return result

    def run_batch(self, configs: List[SourceConfig]) -> List[ProfileReport]:
        logger.info("batch_profiling_started", count=len(configs))
        reports = []
        for cfg in configs:
            try:
                res = self.run(cfg)
                if res.get("final_report"):
                    reports.append(res["final_report"])
            except Exception as e:
                logger.error("table_profiling_failed", table=cfg.table, error=str(e))
        
        logger.info("batch_profiling_complete", report_count=len(reports))
        return reports
ch_profiling_complete", report_count=len(reports))
        return reports
