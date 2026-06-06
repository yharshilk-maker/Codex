-- Work Order Turnaround Time
-- Average days from open to close, grouped by event type and facility,
-- highlighting outliers beyond 2 standard deviations.
-- Demonstrates: date arithmetic, aggregate functions, subquery, HAVING.

WITH turnaround AS (
    SELECT
        work_order_id,
        event_type,
        facility,
        JULIANDAY(close_date) - JULIANDAY(open_date) AS days_to_close
    FROM work_orders
    WHERE close_date IS NOT NULL
),
stats AS (
    SELECT
        event_type,
        facility,
        COUNT(*)                    AS wo_count,
        ROUND(AVG(days_to_close), 1)  AS avg_days,
        ROUND(MIN(days_to_close), 1)  AS min_days,
        ROUND(MAX(days_to_close), 1)  AS max_days,
        AVG(days_to_close)            AS mean_val,
        AVG(days_to_close * days_to_close) AS mean_sq
    FROM turnaround
    GROUP BY event_type, facility
)
SELECT
    event_type,
    facility,
    wo_count,
    avg_days,
    min_days,
    max_days,
    ROUND(SQRT(mean_sq - mean_val * mean_val), 1) AS stddev_days,
    CASE
        WHEN max_days > AVG(avg_days) OVER (PARTITION BY event_type)
             + 2 * SQRT(mean_sq - mean_val * mean_val)
        THEN 'OUTLIER'
        ELSE 'NORMAL'
    END AS outlier_flag
FROM stats
ORDER BY event_type, avg_days DESC;
