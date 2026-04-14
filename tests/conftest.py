import pytest
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip
import os

@pytest.fixture(scope="session")
def spark():
    """
    Creates a local SparkSession for testing.
    """
    builder = (
        SparkSession.builder
        .master("local[1]")
        .appName("PyTest-DataProfiling")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()
