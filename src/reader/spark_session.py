import os
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip

def get_spark_session(app_name: str = "DataProfilingAgent"):
    """
    Factory for SparkSession with Delta Lake support.
    """
    master = os.getenv("SPARK_MASTER", "local[*]")
    
    builder = (
        SparkSession.builder
        .appName(app_name)
        .master(master)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Optimization: Use larger memory if available
        .config("spark.driver.memory", "4g")
    )

    # Add Delta Lake packages automatically
    return configure_spark_with_delta_pip(builder).getOrCreate()
