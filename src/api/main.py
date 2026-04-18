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

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize heavyweight resources (Spark session, ProfilingAgent, DeltaWriter).
    """
    model_name = os.getenv("LLM_PROVIDER", "gemini/gemini-2.5-flash")
    logger.info("api_startup", model_name=model_name)
    app.state.agent = ProfilingAgent(model_name=model_name)
    app.state.writer = DeltaWriter()
    yield

app = FastAPI(title="Data Profiling Agent API", lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "online",
        "agent_version": "2.0.0",
        "model": os.getenv("LLM_PROVIDER", "gemini/gemini-2.5-flash")
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
        logger.info("api_trigger_profile", table=config.table, connection=config.connection_type)
        
        result = await run_in_threadpool(request.app.state.agent.run, config)
        
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
        logger.info("api_trigger_batch_profile", count=len(configs))
        
        reports = await run_in_threadpool(request.app.state.agent.run_batch, configs)
        
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
