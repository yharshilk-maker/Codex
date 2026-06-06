CREATE TABLE IF NOT EXISTS engines (
    engine_id       TEXT PRIMARY KEY,
    engine_model    TEXT NOT NULL,
    fleet           TEXT NOT NULL,
    manufacture_date DATE NOT NULL,
    total_flight_hours REAL DEFAULT 0,
    status          TEXT CHECK(status IN ('Active', 'In MRO', 'Retired')) DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS parts (
    part_id         TEXT PRIMARY KEY,
    part_name       TEXT NOT NULL,
    part_category   TEXT NOT NULL,
    mean_time_between_failure_hours REAL,
    unit_cost_usd   REAL
);

CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    engine_id       TEXT NOT NULL REFERENCES engines(engine_id),
    event_type      TEXT CHECK(event_type IN ('Scheduled', 'Unscheduled', 'Inspection', 'Overhaul')),
    open_date       DATE NOT NULL,
    close_date      DATE,
    facility        TEXT,
    technician_id   TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS part_replacements (
    replacement_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id   INTEGER NOT NULL REFERENCES work_orders(work_order_id),
    part_id         TEXT NOT NULL REFERENCES parts(part_id),
    quantity        INTEGER DEFAULT 1,
    reason          TEXT CHECK(reason IN ('Wear', 'Failure', 'Preventive', 'Upgrade')),
    flight_hours_at_replacement REAL
);

CREATE TABLE IF NOT EXISTS flight_logs (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    engine_id       TEXT NOT NULL REFERENCES engines(engine_id),
    log_date        DATE NOT NULL,
    flight_hours_delta REAL NOT NULL,
    cycles_delta    INTEGER NOT NULL
);
