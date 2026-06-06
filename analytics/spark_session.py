"""
Spark session factory for sustainment analytics.

Local usage:
    from analytics.spark_session import create_spark_session
    spark = create_spark_session()

Databricks usage:
    In a Databricks notebook the SparkSession is pre-created as `spark`.
    Skip this module and pass the existing `spark` object to the analytics
    functions. Change CSV paths to DBFS paths, e.g.:
        "/dbfs/FileStore/tables/engines.csv"
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV_DIR = os.path.join(PROJECT_ROOT, "data", "csv")

# PySpark requires Java 17; if a local install exists, prefer it over the system default
_JAVA17_PATH = os.path.expanduser("~/java/jdk-17.0.19+10/Contents/Home")
if os.path.isdir(_JAVA17_PATH) and "JAVA_HOME" not in os.environ:
    os.environ["JAVA_HOME"] = _JAVA17_PATH
    os.environ["PATH"] = os.path.join(_JAVA17_PATH, "bin") + os.pathsep + os.environ.get("PATH", "")


def create_spark_session(app_name="sustainment-analytics"):
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder
        .master("local[*]")
        .appName(app_name)
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_tables(spark, csv_dir=None):
    """Load all 5 tables from CSV into Spark DataFrames."""
    if csv_dir is None:
        csv_dir = DEFAULT_CSV_DIR

    tables = {}
    for name in ["engines", "parts", "work_orders", "part_replacements", "flight_logs"]:
        path = os.path.join(csv_dir, f"{name}.csv")
        tables[name] = spark.read.csv(path, header=True, inferSchema=True)

    return tables
