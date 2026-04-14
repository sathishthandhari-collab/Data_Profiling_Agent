from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

class ColumnSchema(BaseModel):
    name: str
    spark_type: str
    nullable: bool
    is_pk_candidate: bool = False
    uniqueness_ratio: float = 0.0

class StatsProfile(BaseModel):
    column: str
    null_pct: float
    cardinality_est: int
    min_val: Optional[Union[int, float, str]] = None
    max_val: Optional[Union[int, float, str]] = None
    mean_val: Optional[float] = None
    stddev_val: Optional[float] = None
    has_outliers: bool = False

class PIIProfile(BaseModel):
    column: str
    is_pii: bool
    pii_type: Optional[str] = None  # e.g., "EMAIL", "SSN", "NAME"
    confidence: float = 0.0

class BKCandidate(BaseModel):
    column: str
    confidence: float  # 0.0 – 1.0
    reasoning: str

class FKHint(BaseModel):
    source_col: str
    target_table: str
    target_col: str
    match_ratio: float

class LLMInterpretation(BaseModel):
    suggested_entity_name: str
    bk_candidates: List[BKCandidate]
    pii_summary: List[str]
    dq_flags: List[str]
    confidence: float

class ProfileReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_table: str
    source_system: str  # e.g. "core_banking", "loan_origination"
    profiled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int
    columns: List[ColumnSchema]
    stats: List[StatsProfile]
    pii_info: List[PIIProfile]
    fk_hints: List[FKHint]
    interpretation: Optional[LLMInterpretation] = None
    schema_version: str = "1.1.0"
