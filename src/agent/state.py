from typing import List, Dict, Optional, Any, TypedDict
from pyspark.sql import DataFrame
from src.models.profile_report import (
    ColumnSchema, 
    StatsProfile, 
    PIIProfile, 
    FKHint, 
    LLMInterpretation, 
    ProfileReport
)
from src.models.source_config import SourceConfig

class AgentState(TypedDict):
    # Inputs
    source_config: SourceConfig
    request_source: Optional[str]
    
    # Internal Data
    df: DataFrame
    df_rows_count: int
    original_row_count: Optional[int]
    column_schemas: List[ColumnSchema]
    stats_profiles: List[StatsProfile]
    pii_profiles: List[PIIProfile]
    fk_hints: List[FKHint]
    detected_patterns: Dict[str, Any]  # Updated to Any for new PatternTool results
    
    # Processed Data (for LLM)
    summarized_stats: List[Dict[str, Any]]
    
    # Output
    interpretation: Optional[LLMInterpretation]
    final_report: Optional[ProfileReport]
    errors: List[str]
