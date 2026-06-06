-- Engine Lifecycle Dashboard Query
-- Comprehensive per-engine row: total flight hours, total cycles, count of each
-- work order type, total parts cost, and days since last overhaul.
-- Demonstrates: JOIN across 3+ tables, CASE aggregation, subquery, date arithmetic.

SELECT
    e.engine_id,
    e.engine_model,
    e.fleet,
    e.status,
    ROUND(e.total_flight_hours, 1) AS total_flight_hours,
    COALESCE(fl.total_cycles, 0)   AS total_cycles,
    COALESCE(wo_counts.scheduled_count, 0)   AS scheduled_wo,
    COALESCE(wo_counts.unscheduled_count, 0) AS unscheduled_wo,
    COALESCE(wo_counts.inspection_count, 0)  AS inspection_wo,
    COALESCE(wo_counts.overhaul_count, 0)    AS overhaul_wo,
    COALESCE(ROUND(costs.total_parts_cost, 2), 0) AS total_parts_cost,
    last_oh.days_since_overhaul
FROM engines e
LEFT JOIN (
    SELECT engine_id, SUM(cycles_delta) AS total_cycles
    FROM flight_logs
    GROUP BY engine_id
) fl ON e.engine_id = fl.engine_id
LEFT JOIN (
    SELECT
        engine_id,
        SUM(CASE WHEN event_type = 'Scheduled' THEN 1 ELSE 0 END)   AS scheduled_count,
        SUM(CASE WHEN event_type = 'Unscheduled' THEN 1 ELSE 0 END) AS unscheduled_count,
        SUM(CASE WHEN event_type = 'Inspection' THEN 1 ELSE 0 END)  AS inspection_count,
        SUM(CASE WHEN event_type = 'Overhaul' THEN 1 ELSE 0 END)    AS overhaul_count
    FROM work_orders
    GROUP BY engine_id
) wo_counts ON e.engine_id = wo_counts.engine_id
LEFT JOIN (
    SELECT
        wo.engine_id,
        SUM(pr.quantity * p.unit_cost_usd) AS total_parts_cost
    FROM work_orders wo
    JOIN part_replacements pr ON wo.work_order_id = pr.work_order_id
    JOIN parts p ON pr.part_id = p.part_id
    GROUP BY wo.engine_id
) costs ON e.engine_id = costs.engine_id
LEFT JOIN (
    SELECT
        engine_id,
        CAST(JULIANDAY('now') - JULIANDAY(MAX(close_date)) AS INTEGER) AS days_since_overhaul
    FROM work_orders
    WHERE event_type = 'Overhaul' AND close_date IS NOT NULL
    GROUP BY engine_id
) last_oh ON e.engine_id = last_oh.engine_id
ORDER BY e.engine_id;
