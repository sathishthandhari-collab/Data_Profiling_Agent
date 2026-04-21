import os
import structlog
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip

logger = structlog.get_logger(__name__)

def get_spark_session(app_name: str = "DataProfilingAgent"):
    """
    Factory for SparkSession with Delta Lake support or Databricks Connect.
    """
    # Use Databricks Connect if configured
    if os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN"):
        try:
            from databricks.connect import DatabricksSession
            logger.info("creating_databricks_session")
            # DatabricksSession automatically uses the DATABRICKS_* environment variables
            # It will connect to serverless or to the cluster specified in DATABRICKS_CLUSTER_ID
            return DatabricksSession.builder.getOrCreate()
        except ImportError:
            logger.warning("databricks_connect_not_installed_falling_back_to_local_spark")

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
