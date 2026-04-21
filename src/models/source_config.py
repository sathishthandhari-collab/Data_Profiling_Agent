from typing import Optional, Dict, Literal
from pydantic import BaseModel, Field

class SourceConfig(BaseModel):
    """
    Describes what to profile.

    Current UI/API primarily uses database/table semantics (duckdb/databricks).
    For file-based workflows, set `path` (and optionally `format`).
    """

    name: str
    source_system: str = "LoanIQ"
    execution_mode: Literal["deep", "observability"] = "deep"
    incremental_timestamp_col: Optional[str] = None

    # DB/table style config (current Streamlit payload)
    database: str = "banking"
    table: str
    connection_type: Literal[
        "duckdb",
        "databricks",
        "delta",
        "parquet",
        "csv",
        "file",
    ] = "duckdb"

    # File-based config (optional)
    path: Optional[str] = None
    format: Optional[Literal["delta", "parquet", "csv"]] = None

    # Reader-specific options (e.g. delimiter/header/inferSchema)
    options: Dict[str, str] = Field(default_factory=dict)
