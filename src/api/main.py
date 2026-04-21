import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from typing import List

from src.models.source_config import SourceConfig
from src.agent.profiling_agent import ProfilingAgent
from src.output.delta_writer import DeltaWriter
from src.models.profile_report import ProfileReport
from src.models.evaluation import EvaluationSample

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize heavyweight resources (Spark session, ProfilingAgent, DeltaWriter).
    """
    model_name = os.getenv("LLM_PROVIDER", "gemini/gemini-3.0-flash")
    logger.info("api_startup", model_name=model_name)
    app.state.agent = ProfilingAgent(model_name=model_name)
    app.state.writer = DeltaWriter()
    yield

app = FastAPI(title="Data Profiling Agent API", lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "online",
        "agent_version": "3.0.0",
        "model": os.getenv("LLM_PROVIDER", "gemini/gemini-3.0-flash")
    }

@app.get("/")
async def root():
    return {"status": "online", "message": "Data Profiling Agent is ready"}

@app.post("/profile", response_model=ProfileReport)
async def trigger_profile(config: SourceConfig, request: Request):
    """
    Triggers profiling for a single table.
    """
    try:
        req_source = request.headers.get("x-request-source")
        logger.info("api_trigger_profile", table=config.table, connection=config.connection_type, request_source=req_source)
        
        result = await run_in_threadpool(request.app.state.agent.run, config, req_source)
        
        if not result.get("final_report"):
            raise HTTPException(status_code=500, detail="Agent failed to produce a report")

        report = result["final_report"]
        await run_in_threadpool(request.app.state.writer.write_report, report)

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_profile_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/profile/batch", response_model=List[ProfileReport])
async def trigger_batch_profile(configs: List[SourceConfig], request: Request):
    """
    Triggers batch profiling for multiple tables.
    """
    try:
        req_source = request.headers.get("x-request-source")
        logger.info("api_trigger_batch_profile", count=len(configs), request_source=req_source)
        
        reports = await run_in_threadpool(request.app.state.agent.run_batch, configs, req_source)
        
        for report in reports:
            await run_in_threadpool(request.app.state.writer.write_report, report)
            
        return reports

    except Exception as e:
        logger.error("api_batch_profile_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/{report_id}")
async def get_report(report_id: str, request: Request):
    """
    Retrieves a profiling report by ID.
    """
    try:
        report = await run_in_threadpool(request.app.state.writer.get_report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_get_report_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tables")
async def list_tables(request: Request, schema: str = None):
    """
    Lists tables available in Databricks Unity Catalog (catalog.schema).
    Falls back to local delta directories if not on Databricks.
    """
    import os
    from pathlib import Path

    catalog = os.getenv("DATABRICKS_CATALOG", "")
    schema = schema or os.getenv("DATABRICKS_SCHEMA", "")

    if catalog and schema:
        try:
            spark = request.app.state.agent.reader.spark
            rows = await run_in_threadpool(
                lambda: spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema}`").collect()
            )
            return {"tables": [r["tableName"] for r in rows]}
        except Exception as e:
            logger.error("list_tables_databricks_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # Local fallback
    data_root = Path(os.getenv("DATA_PATH", "data"))
    delta_base = data_root / "delta"
    if delta_base.exists():
        tables = [
            d.name for d in delta_base.iterdir()
            if d.is_dir() and d.name not in {"profiling_reports"} and not d.name.endswith("_index")
        ]
        return {"tables": tables}

    return {"tables": []}


@app.get("/eval/dataset", response_model=List[EvaluationSample])
async def get_eval_dataset():
    """
    Returns Agent 7 golden datasets for evaluation testing.
    """
    import os
    import json
    from pathlib import Path
    
    golden_dir = Path("tests/fixtures/golden")
    samples = []
    
    if golden_dir.exists():
        for f in golden_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                samples.append(EvaluationSample(**data))
            except Exception as e:
                logger.error("failed_parsing_golden_dataset", file=f.name, error=str(e))
                
    return samples
