from fastapi import FastAPI, HTTPException
from src.models.source_config import SourceConfig
from src.agent.profiling_agent import ProfilingAgent
from src.output.delta_writer import DeltaWriter
from src.models.profile_report import ProfileReport

app = FastAPI(title="Data Profiling Agent API")
agent = ProfilingAgent()
writer = DeltaWriter()

@app.get("/")
async def root():
    return {"status": "online", "message": "Data Profiling Agent is ready"}

@app.post("/profile", response_model=ProfileReport)
async def trigger_profile(config: SourceConfig):
    """
    Triggers the profiling agent for the given source configuration.
    """
    try:
        loc = config.path or f"{config.database}.{config.table}"
        print(f"🚀 API: Triggering profile for {config.name} from {loc} (type={config.connection_type})")
        
        # Run the LangGraph Agent
        result = agent.run(config)
        
        if not result.get("final_report"):
            raise HTTPException(status_code=500, detail="Agent failed to produce a report")
        
        report = result["final_report"]
        
        # Persist to Delta
        writer.write_report(report)
        
        return report
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/{report_id}")
async def get_report(report_id: str):
    """
    Retrieves a profiling report from Delta Lake.
    """
    try:
        report = writer.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
