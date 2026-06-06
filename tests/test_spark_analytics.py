"""Tests for the 5 PySpark analytics functions."""

import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def spark_and_tables():
    from data_generator.generate import run as generate_data
    from analytics.spark_session import create_spark_session, load_tables

    db_path = os.path.join(PROJECT_ROOT, "data", "test_spark.db")
    csv_dir = os.path.join(PROJECT_ROOT, "data", "csv_spark_test")
    generate_data(db_path=db_path, csv_dir=csv_dir, num_engines=50, seed=77)

    spark = create_spark_session("test-sustainment-analytics")
    tables = load_tables(spark, csv_dir)
    yield spark, tables
    spark.stop()

    if os.path.exists(db_path):
        os.remove(db_path)


def test_failure_rate_heatmap_nonempty(spark_and_tables):
    from analytics.fleet_analytics import failure_rate_heatmap
    spark, tables = spark_and_tables
    df = failure_rate_heatmap(spark, tables)
    assert df.count() > 0
    assert "engine_model" in df.columns
    assert "failure_count" in df.columns


def test_part_lifecycle_curve_nonempty(spark_and_tables):
    from analytics.fleet_analytics import part_lifecycle_curve
    spark, tables = spark_and_tables
    df = part_lifecycle_curve(spark, tables)
    assert df.count() > 0
    assert "survival_pct" in df.columns
    rows = df.collect()
    for r in rows:
        assert r["survival_pct"] >= 0


def test_maintenance_cost_forecast_nonempty(spark_and_tables):
    from analytics.fleet_analytics import maintenance_cost_forecast
    spark, tables = spark_and_tables
    df = maintenance_cost_forecast(spark, tables)
    assert df.count() > 0
    assert "rolling_6m_avg" in df.columns


def test_fleet_availability_score(spark_and_tables):
    from analytics.fleet_analytics import fleet_availability_score
    spark, tables = spark_and_tables
    df = fleet_availability_score(spark, tables)
    assert df.count() > 0
    rows = df.collect()
    for r in rows:
        assert 0 <= r["availability_pct"] <= 100


def test_anomaly_detection_flags(spark_and_tables):
    from analytics.fleet_analytics import anomaly_detection_flags
    spark, tables = spark_and_tables
    df = anomaly_detection_flags(spark, tables)
    assert df.count() > 0
    total_replacements = tables["part_replacements"].count()
    assert df.count() <= total_replacements


def test_anomaly_flags_are_premature(spark_and_tables):
    from analytics.fleet_analytics import anomaly_detection_flags
    spark, tables = spark_and_tables
    df = anomaly_detection_flags(spark, tables)
    rows = df.collect()
    for r in rows:
        assert r["ratio_to_mtbf"] <= 0.5
