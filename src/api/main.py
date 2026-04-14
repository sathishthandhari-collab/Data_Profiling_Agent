from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from src.models.source_config import SourceConfig
from src.agent.profiling_agent import ProfilingAgent
from src.output.delta_writer import DeltaWriter
from src.models.profile_report import ProfileReport


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize heavyweight resources (Spark session, ProfilingAgent, DeltaWriter)
    during application startup rather than at module import time.

    Benefits:
    - Spark only starts when the API actually boots, not during test imports.
    - Startup failures are isolated to the lifespan context and surfaced clearly.
    - Resources are naturally scoped to the application lifetime.
    """
    app.state.agent = ProfilingAgent()
    app.state.writer = DeltaWriter()
    yield
    # No explicit teardown needed; the Spark JVM shuts down with the process.


app = FastAPI(title="Data Profiling Agent API", lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "online", "message": "Data Profiling Agent is ready"}


@app.post("/profile", response_model=ProfileReport)
async def trigger_profile(config: SourceConfig, request: Request):
    """
    Triggers the profiling agent for the given source configuration.

    The Spark/LangGraph workload is dispatched to a thread pool via
    run_in_threadpool so the FastAPI event loop is never blocked.
    """
    try:
        loc = config.path or f"{config.database}.{config.table}"
        print(f"🚀 API: Triggering profile for {config.name} from {loc} (type={config.connection_type})")

        # Run the synchronous LangGraph + Spark workload off the async event loop.
        result = await run_in_threadpool(request.app.state.agent.run, config)

        if not result.get("final_report"):
            raise HTTPException(status_code=500, detail="Agent failed to produce a report")

        report = result["final_report"]

        # Persist to Delta (Spark write is also synchronous — run in thread pool).
        await run_in_threadpool(request.app.state.writer.write_report, report)

        # Surface any non-fatal errors that occurred during profiling.
        if errors := result.get("errors"):
            print(f"⚠️  Non-fatal errors during profiling of {config.name}: {errors}")

        return report

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/{report_id}")
async def get_report(report_id: str, request: Request):
    """
    Retrieves a profiling report by ID.
    Uses the sidecar JSON fast path; falls back to a Delta scan if needed.
    """
    try:
        report = await run_in_threadpool(request.app.state.writer.get_report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
