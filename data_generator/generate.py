"""Synthetic data generator for engine fleet sustainment analytics."""

import sqlite3
import csv
import os
import sys
from datetime import datetime, timedelta

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENGINE_MODELS = {
    "PW1100G": {"fleet": "Commercial", "hours_per_year": (3000, 4500)},
    "F135": {"fleet": "Military", "hours_per_year": (800, 1500)},
    "PW4000": {"fleet": "Commercial", "hours_per_year": (2500, 4000)},
}

PARTS_CATALOG = [
    ("PRT-001", "High-Pressure Turbine Blade", "Hot Section", 6000, 12500),
    ("PRT-002", "Low-Pressure Turbine Blade", "Hot Section", 8000, 8700),
    ("PRT-003", "Combustion Liner", "Hot Section", 7000, 15000),
    ("PRT-004", "Fuel Nozzle", "Hot Section", 10000, 4200),
    ("PRT-005", "Turbine Disk", "Hot Section", 15000, 45000),
    ("PRT-006", "Fan Blade", "Fan", 12000, 18000),
    ("PRT-007", "Fan Case", "Fan", 25000, 32000),
    ("PRT-008", "Fan Hub", "Fan", 20000, 22000),
    ("PRT-009", "Inlet Guide Vane", "Fan", 14000, 6500),
    ("PRT-010", "Bearing Assembly - Front", "Bearings", 10000, 9800),
    ("PRT-011", "Bearing Assembly - Rear", "Bearings", 10000, 9800),
    ("PRT-012", "Main Gearbox", "Gearbox", 18000, 55000),
    ("PRT-013", "Accessory Gearbox", "Gearbox", 15000, 28000),
    ("PRT-014", "Oil Pump", "Gearbox", 12000, 7600),
    ("PRT-015", "Compressor Rotor Stage 1", "Compressor", 16000, 21000),
    ("PRT-016", "Compressor Stator Vane", "Compressor", 14000, 11500),
    ("PRT-017", "Bleed Valve", "Compressor", 11000, 3800),
    ("PRT-018", "FADEC Unit", "Controls", 20000, 62000),
    ("PRT-019", "Igniter Plug", "Hot Section", 5000, 1200),
    ("PRT-020", "Exhaust Nozzle Segment", "Exhaust", 9000, 8900),
]

FACILITIES = [
    "East Hartford MRO", "Columbus Engine Center", "San Antonio Depot",
    "Singapore MRO Hub", "Berlin Overhaul Facility",
]

TECHNICIANS = [f"TECH-{i:03d}" for i in range(1, 31)]


def generate_engines(rng, num_engines=50):
    engines = []
    models = list(ENGINE_MODELS.keys())
    weights = [0.45, 0.20, 0.35]
    for i in range(num_engines):
        model = rng.choice(models, p=weights)
        info = ENGINE_MODELS[model]
        manufacture_year = rng.integers(2015, 2023)
        manufacture_month = rng.integers(1, 13)
        manufacture_date = datetime(manufacture_year, manufacture_month, 1)
        engines.append({
            "engine_id": f"ENG-{i+1:03d}",
            "engine_model": model,
            "fleet": info["fleet"],
            "manufacture_date": manufacture_date.strftime("%Y-%m-%d"),
            "total_flight_hours": 0.0,
            "status": "Active",
        })
    return engines


def generate_parts():
    return [
        {
            "part_id": p[0],
            "part_name": p[1],
            "part_category": p[2],
            "mean_time_between_failure_hours": float(p[3]),
            "unit_cost_usd": float(p[4]),
        }
        for p in PARTS_CATALOG
    ]


def generate_flight_logs(rng, engines, end_date):
    """Generate biweekly flight logs for each engine, accumulating hours and cycles."""
    logs = []
    engine_hours = {}
    engine_cycles = {}

    for eng in engines:
        eid = eng["engine_id"]
        model = eng["engine_model"]
        mfg = datetime.strptime(eng["manufacture_date"], "%Y-%m-%d")
        info = ENGINE_MODELS[model]
        low, high = info["hours_per_year"]
        hours_per_day = rng.uniform(low / 365, high / 365)

        current = mfg + timedelta(days=14)
        total_hours = 0.0
        total_cycles = 0

        while current <= end_date:
            delta_days = 14
            fh = max(0, rng.normal(hours_per_day * delta_days, hours_per_day * delta_days * 0.15))
            cycles = max(1, int(rng.poisson(fh / 2.5)))
            total_hours += fh
            total_cycles += cycles
            logs.append({
                "engine_id": eid,
                "log_date": current.strftime("%Y-%m-%d"),
                "flight_hours_delta": round(fh, 1),
                "cycles_delta": cycles,
            })
            current += timedelta(days=delta_days)

        engine_hours[eid] = round(total_hours, 1)
        engine_cycles[eid] = total_cycles

    return logs, engine_hours, engine_cycles


def generate_work_orders(rng, engines, engine_hours, end_date, history_years=3):
    """Generate work orders with realistic frequency distributions."""
    work_orders = []
    wo_id = 0
    engine_wo_map = {e["engine_id"]: [] for e in engines}

    for eng in engines:
        eid = eng["engine_id"]
        model = eng["engine_model"]
        mfg = datetime.strptime(eng["manufacture_date"], "%Y-%m-%d")
        start = max(mfg, end_date - timedelta(days=history_years * 365))
        hours = engine_hours.get(eid, 0)

        age_years = (end_date - mfg).days / 365.0
        base_rate = 4 if model == "F135" else 3
        annual_rate = base_rate + max(0, age_years - 3) * 0.8
        num_wo = max(2, int(rng.poisson(annual_rate * history_years)))

        for _ in range(num_wo):
            wo_id += 1
            open_dt = start + timedelta(days=int(rng.uniform(0, (end_date - start).days)))

            type_weights = [0.30, 0.25, 0.30, 0.15]
            if age_years > 5:
                type_weights = [0.25, 0.35, 0.20, 0.20]
            event_type = rng.choice(
                ["Scheduled", "Unscheduled", "Inspection", "Overhaul"], p=type_weights
            )

            turnaround = {
                "Scheduled": rng.integers(3, 15),
                "Unscheduled": rng.integers(5, 30),
                "Inspection": rng.integers(1, 5),
                "Overhaul": rng.integers(30, 90),
            }[event_type]
            close_dt = open_dt + timedelta(days=int(turnaround))

            facility = rng.choice(FACILITIES)
            tech = rng.choice(TECHNICIANS)

            wo = {
                "engine_id": eid,
                "event_type": event_type,
                "open_date": open_dt.strftime("%Y-%m-%d"),
                "close_date": close_dt.strftime("%Y-%m-%d"),
                "facility": facility,
                "technician_id": tech,
                "notes": f"{event_type} maintenance for {model}",
            }
            work_orders.append(wo)
            engine_wo_map[eid].append((wo_id, open_dt, event_type, hours))

    return work_orders, engine_wo_map


def generate_part_replacements(rng, work_orders, engine_wo_map, engine_hours, parts):
    """Generate part replacements linked to work orders, ensuring hour consistency."""
    replacements = []
    parts_by_id = {p["part_id"]: p for p in parts}
    part_ids = [p["part_id"] for p in parts]

    for wo_idx, wo in enumerate(work_orders):
        wo_id = wo_idx + 1
        eid = wo["engine_id"]
        event_type = wo["event_type"]
        max_hours = engine_hours.get(eid, 0)

        num_parts = {
            "Scheduled": rng.integers(1, 4),
            "Unscheduled": rng.integers(1, 3),
            "Inspection": rng.integers(0, 2),
            "Overhaul": rng.integers(3, 8),
        }[event_type]

        selected = rng.choice(part_ids, size=min(num_parts, len(part_ids)), replace=False)
        for pid in selected:
            part = parts_by_id[pid]
            mtbf = part["mean_time_between_failure_hours"]
            fh = min(max_hours, max(0, rng.normal(mtbf * 0.8, mtbf * 0.2)))
            fh = round(fh, 1)

            reason_weights = {
                "Scheduled": [0.4, 0.1, 0.4, 0.1],
                "Unscheduled": [0.2, 0.6, 0.1, 0.1],
                "Inspection": [0.3, 0.2, 0.4, 0.1],
                "Overhaul": [0.2, 0.1, 0.5, 0.2],
            }[event_type]
            reason = rng.choice(["Wear", "Failure", "Preventive", "Upgrade"], p=reason_weights)

            replacements.append({
                "work_order_id": wo_id,
                "part_id": pid,
                "quantity": int(rng.integers(1, 4)),
                "reason": reason,
                "flight_hours_at_replacement": fh,
            })

    return replacements


def insert_data(db_path, schema_path, engines, parts, work_orders, part_replacements, flight_logs):
    """Insert all generated data into SQLite using parameterized queries."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    with open(schema_path, "r") as f:
        cursor.executescript(f.read())

    cursor.executemany(
        "INSERT INTO engines VALUES (?, ?, ?, ?, ?, ?)",
        [(e["engine_id"], e["engine_model"], e["fleet"], e["manufacture_date"],
          e["total_flight_hours"], e["status"]) for e in engines],
    )

    cursor.executemany(
        "INSERT INTO parts VALUES (?, ?, ?, ?, ?)",
        [(p["part_id"], p["part_name"], p["part_category"],
          p["mean_time_between_failure_hours"], p["unit_cost_usd"]) for p in parts],
    )

    cursor.executemany(
        "INSERT INTO work_orders (engine_id, event_type, open_date, close_date, facility, technician_id, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(w["engine_id"], w["event_type"], w["open_date"], w["close_date"],
          w["facility"], w["technician_id"], w["notes"]) for w in work_orders],
    )

    cursor.executemany(
        "INSERT INTO part_replacements (work_order_id, part_id, quantity, reason, flight_hours_at_replacement) "
        "VALUES (?, ?, ?, ?, ?)",
        [(r["work_order_id"], r["part_id"], r["quantity"], r["reason"],
          r["flight_hours_at_replacement"]) for r in part_replacements],
    )

    cursor.executemany(
        "INSERT INTO flight_logs (engine_id, log_date, flight_hours_delta, cycles_delta) "
        "VALUES (?, ?, ?, ?)",
        [(f["engine_id"], f["log_date"], f["flight_hours_delta"], f["cycles_delta"])
         for f in flight_logs],
    )

    conn.commit()

    cursor.execute("UPDATE engines SET total_flight_hours = ("
                   "SELECT COALESCE(SUM(flight_hours_delta), 0) FROM flight_logs "
                   "WHERE flight_logs.engine_id = engines.engine_id)")

    num_engines = cursor.execute("SELECT COUNT(*) FROM engines").fetchone()[0]
    mro_count = max(1, int(num_engines * 0.15))
    retired_count = max(1, int(num_engines * 0.06))
    cursor.execute(
        f"UPDATE engines SET status = 'In MRO' WHERE engine_id IN "
        f"(SELECT engine_id FROM engines ORDER BY total_flight_hours DESC LIMIT {mro_count})"
    )
    cursor.execute(
        f"UPDATE engines SET status = 'Retired' WHERE engine_id IN "
        f"(SELECT engine_id FROM engines WHERE status = 'Active' "
        f"ORDER BY manufacture_date ASC LIMIT {retired_count})"
    )

    conn.commit()
    conn.close()


def export_csvs(db_path, csv_dir):
    """Export each table to CSV for Spark/Databricks ingestion."""
    os.makedirs(csv_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    tables = ["engines", "parts", "work_orders", "part_replacements", "flight_logs"]

    for table in tables:
        cursor = conn.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        with open(os.path.join(csv_dir, f"{table}.csv"), "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

    conn.close()


def run(db_path=None, csv_dir=None, num_engines=50, num_parts=20, history_years=3, seed=42):
    schema_path = os.path.join(PROJECT_ROOT, "database", "schema.sql")
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "sustainment.db")
    if csv_dir is None:
        csv_dir = os.path.join(PROJECT_ROOT, "data", "csv")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    rng = np.random.default_rng(seed)
    end_date = datetime(2026, 6, 1)

    print("Generating engines...")
    engines = generate_engines(rng, num_engines)

    print("Generating parts catalog...")
    parts = generate_parts()

    print("Generating flight logs...")
    flight_logs, engine_hours, engine_cycles = generate_flight_logs(rng, engines, end_date)

    print("Generating work orders...")
    work_orders, engine_wo_map = generate_work_orders(rng, engines, engine_hours, end_date, history_years)

    print("Generating part replacements...")
    part_replacements = generate_part_replacements(rng, work_orders, engine_wo_map, engine_hours, parts)

    print("Inserting into database...")
    insert_data(db_path, schema_path, engines, parts, work_orders, part_replacements, flight_logs)

    print("Exporting CSVs...")
    export_csvs(db_path, csv_dir)

    print(f"\nGeneration complete:")
    print(f"  Engines:            {len(engines)}")
    print(f"  Parts:              {len(parts)}")
    print(f"  Work Orders:        {len(work_orders)}")
    print(f"  Part Replacements:  {len(part_replacements)}")
    print(f"  Flight Logs:        {len(flight_logs)}")
    print(f"  Database:           {db_path}")
    print(f"  CSVs:               {csv_dir}")

    return db_path


if __name__ == "__main__":
    run()
