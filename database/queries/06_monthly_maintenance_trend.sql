-- Monthly Maintenance Trend
-- Time-series of work order counts by month and event type.
-- Uses a CTE for the date spine to ensure months with zero events still appear.
-- Demonstrates: CTE, LEFT JOIN, date functions, GROUP BY.

WITH RECURSIVE date_spine(month_start) AS (
    SELECT DATE((SELECT MIN(open_date) FROM work_orders), 'start of month')
    UNION ALL
    SELECT DATE(month_start, '+1 month')
    FROM date_spine
    WHERE month_start < (SELECT MAX(open_date) FROM work_orders)
),
event_types(event_type) AS (
    VALUES ('Scheduled'), ('Unscheduled'), ('Inspection'), ('Overhaul')
),
spine AS (
    SELECT
        d.month_start,
        et.event_type
    FROM date_spine d
    CROSS JOIN event_types et
)
SELECT
    s.month_start,
    s.event_type,
    COUNT(wo.work_order_id) AS wo_count
FROM spine s
LEFT JOIN work_orders wo
    ON wo.event_type = s.event_type
   AND DATE(wo.open_date, 'start of month') = s.month_start
GROUP BY s.month_start, s.event_type
ORDER BY s.month_start, s.event_type;
