import pytest
from src.tools.schema_tool import SchemaTool
from src.tools.stats_tool import StatsTool
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

def test_schema_tool_pk_detection(spark):
    """
    Ensures SchemaTool correctly identifies 100% unique, non-null PK candidates.
    """
    data = [
        ("ACC-001", "Checking"),
        ("ACC-002", "Savings"),
        ("ACC-003", "Loan")
    ]
    schema = StructType([
        StructField("id", StringType(), False),  # Not Nullable
        StructField("type", StringType(), True)  # Nullable
    ])
    df = spark.createDataFrame(data, schema)
    
    results = SchemaTool.profile(df, df.count())
    
    # ID should be a PK candidate
    id_profile = next(c for c in results if c.name == "id")
    assert id_profile.is_pk_candidate is True
    assert id_profile.uniqueness_ratio == 1.0

def test_stats_tool_metrics(spark):
    """
    Ensures StatsTool correctly calculates null rates and detects outliers.
    """
    data = [
        (10, 100),
        (20, 200),
        (30, 300),
        (None, 1000000) # One null in col1, one outlier in col2
    ]
    schema = StructType([
        StructField("col1", IntegerType(), True),
        StructField("col2", IntegerType(), True)
    ])
    df = spark.createDataFrame(data, schema)
    
    results = StatsTool.profile(df, df.count())
    
    col1_stats = next(s for s in results if s.column == "col1")
    col2_stats = next(s for s in results if s.column == "col2")
    
    assert col1_stats.null_pct == 0.25
    assert col2_stats.has_outliers is True
