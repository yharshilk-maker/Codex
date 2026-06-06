-- Part Failure Prediction Candidates
-- Parts approaching 80% of their MTBF without recent replacement.
-- Joins engines, parts, part_replacements, and flight_logs (4 tables).
-- Demonstrates: JOIN across 3+ tables, subquery, date arithmetic.

WITH latest_replacement AS (
    SELECT
        wo.engine_id,
        pr.part_id,
        MAX(pr.flight_hours_at_replacement) AS last_replacement_hours
    FROM part_replacements pr
    JOIN work_orders wo ON pr.work_order_id = wo.work_order_id
    GROUP BY wo.engine_id, pr.part_id
),
engine_current_hours AS (
    SELECT
        engine_id,
        total_flight_hours
    FROM engines
    WHERE status = 'Active'
)
SELECT
    ech.engine_id,
    p.part_id,
    p.part_name,
    p.part_category,
    p.mean_time_between_failure_hours AS mtbf,
    ROUND(ech.total_flight_hours, 1)  AS current_hours,
    ROUND(COALESCE(lr.last_replacement_hours, 0), 1) AS last_replaced_at,
    ROUND(ech.total_flight_hours - COALESCE(lr.last_replacement_hours, 0), 1) AS hours_since_replacement,
    ROUND(
        100.0 * (ech.total_flight_hours - COALESCE(lr.last_replacement_hours, 0))
        / p.mean_time_between_failure_hours, 1
    ) AS pct_of_mtbf
FROM engine_current_hours ech
CROSS JOIN parts p
LEFT JOIN latest_replacement lr
    ON lr.engine_id = ech.engine_id AND lr.part_id = p.part_id
WHERE (ech.total_flight_hours - COALESCE(lr.last_replacement_hours, 0))
      >= 0.8 * p.mean_time_between_failure_hours
ORDER BY pct_of_mtbf DESC;
