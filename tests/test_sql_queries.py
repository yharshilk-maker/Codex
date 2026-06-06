"""Tests for the 10 SQL analytical queries."""

import sqlite3
import os
import glob
import pytest

from data_generator.generate import run as generate_data

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_sql_queries.db")
CSV_DIR = os.path.join(PROJECT_ROOT, "data", "csv_sql_test")
QUERIES_DIR = os.path.join(PROJECT_ROOT, "database", "queries")


@pytest.fixture(scope="module")
def db():
    generate_data(db_path=DB_PATH, csv_dir=CSV_DIR, num_engines=50, seed=99)
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def load_query(filename):
    path = os.path.join(QUERIES_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def test_01_fleet_status_summary(db):
    rows = db.execute(load_query("01_fleet_status_summary.sql")).fetchall()
    assert len(rows) > 0
    fleets = {r[0] for r in rows}
    assert "Commercial" in fleets or "Military" in fleets
    for row in rows:
        assert row[2] > 0  # engine_count


def test_02_costliest_parts(db):
    rows = db.execute(load_query("02_costliest_parts.sql")).fetchall()
    assert len(rows) == 10
    assert rows[0][5] == 1  # cost_rank
    for i in range(1, len(rows)):
        assert rows[i][4] <= rows[i - 1][4]  # descending cost


def test_03_unscheduled_rate_by_model(db):
    rows = db.execute(load_query("03_unscheduled_rate_by_model.sql")).fetchall()
    assert len(rows) > 0
    for row in rows:
        pct = row[3]
        flag = row[4]
        assert 0 <= pct <= 100
        if pct > 30:
            assert flag == "FLAGGED"
        else:
            assert flag == "OK"


def test_04_mean_time_between_replacement(db):
    rows = db.execute(load_query("04_mean_time_between_replacement.sql")).fetchall()
    assert len(rows) == 20  # all parts represented


def test_05_turnaround_time(db):
    rows = db.execute(load_query("05_turnaround_time.sql")).fetchall()
    assert len(rows) > 0
    event_types = {r[0] for r in rows}
    assert "Scheduled" in event_types
    for row in rows:
        assert row[3] >= 0  # avg_days non-negative


def test_06_monthly_maintenance_trend(db):
    rows = db.execute(load_query("06_monthly_maintenance_trend.sql")).fetchall()
    assert len(rows) > 0
    event_types = {r[1] for r in rows}
    assert event_types == {"Scheduled", "Unscheduled", "Inspection", "Overhaul"}


def test_07_failure_prediction_candidates(db):
    rows = db.execute(load_query("07_failure_prediction_candidates.sql")).fetchall()
    for row in rows:
        assert row[8] >= 80.0  # pct_of_mtbf >= 80%


def test_08_cost_per_flight_hour(db):
    rows = db.execute(load_query("08_cost_per_flight_hour.sql")).fetchall()
    assert len(rows) == 3  # three engine models
    for row in rows:
        assert row[3] > 0  # cost_per_flight_hour positive


def test_09_technician_workload(db):
    rows = db.execute(load_query("09_technician_workload.sql")).fetchall()
    assert len(rows) > 0
    for row in rows:
        assert row[1] > 0  # avg_monthly_wo positive
        flag = row[6]
        assert flag in ("UNEVEN", "BALANCED")


def test_10_engine_lifecycle_dashboard(db):
    rows = db.execute(load_query("10_engine_lifecycle_dashboard.sql")).fetchall()
    assert len(rows) == 50  # one row per engine
    for row in rows:
        assert row[4] >= 0  # total_flight_hours non-negative
        assert row[5] >= 0  # total_cycles non-negative


def test_all_query_files_exist():
    expected = [f"{i:02d}_" for i in range(1, 11)]
    files = sorted(os.listdir(QUERIES_DIR))
    sql_files = [f for f in files if f.endswith(".sql")]
    assert len(sql_files) == 10
    for prefix, fname in zip(expected, sql_files):
        assert fname.startswith(prefix)


def test_zero_work_order_engine_in_dashboard(db):
    """Edge case: engine with zero work orders should still appear with count 0."""
    row = db.execute(
        load_query("10_engine_lifecycle_dashboard.sql")
    ).fetchall()
    for r in row:
        assert r[6] is not None  # scheduled_wo should be 0, not NULL
