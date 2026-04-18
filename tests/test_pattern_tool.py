import pytest
from pyspark.sql import Row
from src.tools.pattern_tool import PatternTool

def test_pattern_tool_layers(spark):
    data = [
        Row(account_id="ACC-123456", iban="DE12345678901234567890", email="test@bank.com", notes="Regular customer"),
        Row(account_id="ACC-654321", iban="DE09876543210987654321", email="user@domain.org", notes="High value"),
        Row(account_id="ACC-999999", iban="DE55555555555555555555", email="admin@corp.net", notes="New account")
    ]
    df = spark.createDataFrame(data)
    
    # Use a mock config or the default one created earlier
    tool = PatternTool(config_path="config/patterns.yaml")
    results = tool.profile(df, 3)
    
    # Layer 1: Universal
    assert "iban" in results
    assert "IBAN" in results["iban"]["patterns"]
    assert "email" in results
    assert "EMAIL" in results["email"]["patterns"]
    
    # Layer 2: Custom (from config/patterns.yaml)
    assert "account_id" in results
    assert "ACCOUNT_ID" in results["account_id"]["patterns"]
    
    # Layer 3: Heuristics
    assert "LIKELY_KEY" in results["account_id"]["heuristics"]
    assert results["account_id"]["uniqueness_score"] == 1.0
    assert "HIGH_UNIQUENESS_CANDIDATE" in results["account_id"]["heuristics"]
