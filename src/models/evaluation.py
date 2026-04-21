from pydantic import BaseModel
from src.models.source_config import SourceConfig
from src.models.profile_report import ProfileReport

class EvaluationSample(BaseModel):
    """
    Contract model for Agent 7 (The Auditor). 
    Maps a known input config to the expected golden output profile.
    """
    input: SourceConfig
    expected: ProfileReport
    
    class Config:
        strict = False
