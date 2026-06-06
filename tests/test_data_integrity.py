"""Tests for generated data referential integrity and consistency."""

import sqlite3
import os
import pytest

from data_generator.generate import run as generate_data

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_sustainment.db")
CSV_DIR = os.path.join(PROJECT_ROOT, "data", "csv_test")


@pytest.fixture(scope="module")
def db():
    generate_data(db_path=DB_PATH, csv_dir=CSV_DIR, num_engines=50, seed=42)
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def test_work_orders_reference_valid_engines(db):
    orphans = db.execute(
        "SELECT COUNT(*) FROM work_orders WHERE engine_id NOT IN (SELECT engine_id FROM engines)"
    ).fetchone()[0]
    assert orphans == 0


def test_part_replacements_reference_valid_work_orders(db):
    orphans = db.execute(
        "SELECT COUNT(*) FROM part_replacements "
        "WHERE work_order_id NOT IN (SELECT work_order_id FROM work_orders)"
    ).fetchone()[0]
    assert orphans == 0


def test_part_replacements_reference_valid_parts(db):
    orphans = db.execute(
        "SELECT COUNT(*) FROM part_replacements WHERE part_id NOT IN (SELECT part_id FROM parts)"
    ).fetchone()[0]
    assert orphans == 0


def test_flight_logs_reference_valid_engines(db):
    orphans = db.execute(
        "SELECT COUNT(*) FROM flight_logs WHERE engine_id NOT IN (SELECT engine_id FROM engines)"
    ).fetchone()[0]
    assert orphans == 0


def test_no_close_before_open(db):
    bad = db.execute(
        "SELECT COUNT(*) FROM work_orders WHERE close_date < open_date"
    ).fetchone()[0]
    assert bad == 0


def test_replacement_hours_within_engine_hours(db):
    bad = db.execute(
        "SELECT COUNT(*) FROM part_replacements pr "
        "JOIN work_orders wo ON pr.work_order_id = wo.work_order_id "
        "JOIN engines e ON wo.engine_id = e.engine_id "
        "WHERE pr.flight_hours_at_replacement > e.total_flight_hours + 1"
    ).fetchone()[0]
    assert bad == 0


def test_all_engines_have_flight_logs(db):
    missing = db.execute(
        "SELECT COUNT(*) FROM engines "
        "WHERE engine_id NOT IN (SELECT DISTINCT engine_id FROM flight_logs)"
    ).fetchone()[0]
    assert missing == 0


def test_minimum_record_counts(db):
    engines = db.execute("SELECT COUNT(*) FROM engines").fetchone()[0]
    work_orders = db.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    replacements = db.execute("SELECT COUNT(*) FROM part_replacements").fetchone()[0]
    flight_logs = db.execute("SELECT COUNT(*) FROM flight_logs").fetchone()[0]

    assert engines == 50
    assert work_orders >= 500
    assert replacements >= 1200
    assert flight_logs >= 3000


def test_engine_status_distribution(db):
    statuses = dict(db.execute(
        "SELECT status, COUNT(*) FROM engines GROUP BY status"
    ).fetchall())
    assert "Active" in statuses
    assert "In MRO" in statuses
    for status in statuses:
        assert status in ("Active", "In MRO", "Retired")
