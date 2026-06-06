"""Post-generation validation for referential integrity and data consistency."""

import sqlite3
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate(db_path=None):
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "sustainment.db")

    if not os.path.exists(db_path):
        print(f"FAIL: Database not found at {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    passed = 0
    failed = 0

    def check(name, query, expect_zero=True):
        nonlocal passed, failed
        result = cursor.execute(query).fetchone()[0]
        ok = (result == 0) if expect_zero else (result > 0)
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        else:
            passed += 1
        print(f"  [{status}] {name}: {result}")
        return ok

    print("=== Referential Integrity Checks ===")
    check(
        "Work orders → engines FK",
        "SELECT COUNT(*) FROM work_orders WHERE engine_id NOT IN (SELECT engine_id FROM engines)",
    )
    check(
        "Part replacements → work orders FK",
        "SELECT COUNT(*) FROM part_replacements WHERE work_order_id NOT IN (SELECT work_order_id FROM work_orders)",
    )
    check(
        "Part replacements → parts FK",
        "SELECT COUNT(*) FROM part_replacements WHERE part_id NOT IN (SELECT part_id FROM parts)",
    )
    check(
        "Flight logs → engines FK",
        "SELECT COUNT(*) FROM flight_logs WHERE engine_id NOT IN (SELECT engine_id FROM engines)",
    )

    print("\n=== CHECK Constraint Validation ===")
    check(
        "Engine status values",
        "SELECT COUNT(*) FROM engines WHERE status NOT IN ('Active', 'In MRO', 'Retired')",
    )
    check(
        "Work order event types",
        "SELECT COUNT(*) FROM work_orders WHERE event_type NOT IN ('Scheduled', 'Unscheduled', 'Inspection', 'Overhaul')",
    )
    check(
        "Replacement reason values",
        "SELECT COUNT(*) FROM part_replacements WHERE reason NOT IN ('Wear', 'Failure', 'Preventive', 'Upgrade')",
    )

    print("\n=== Temporal Consistency ===")
    check(
        "Work order close >= open",
        "SELECT COUNT(*) FROM work_orders WHERE close_date < open_date",
    )

    print("\n=== Data Consistency ===")
    check(
        "Replacement hours <= engine hours",
        "SELECT COUNT(*) FROM part_replacements pr "
        "JOIN work_orders wo ON pr.work_order_id = wo.work_order_id "
        "JOIN engines e ON wo.engine_id = e.engine_id "
        "WHERE pr.flight_hours_at_replacement > e.total_flight_hours + 1",
    )

    print("\n=== Record Counts ===")
    for table in ["engines", "parts", "work_orders", "part_replacements", "flight_logs"]:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")

    check(
        "Every engine has flight logs",
        "SELECT COUNT(*) FROM engines WHERE engine_id NOT IN (SELECT DISTINCT engine_id FROM flight_logs)",
    )

    conn.close()

    print(f"\n=== Summary: {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
