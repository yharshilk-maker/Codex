-- Technician Workload Distribution
-- Work orders per technician per month, identifying uneven distribution.
-- Demonstrates: date functions, GROUP BY, window functions, aggregate with HAVING.

WITH monthly_workload AS (
    SELECT
        technician_id,
        STRFTIME('%Y-%m', open_date) AS month,
        COUNT(*)                     AS wo_count
    FROM work_orders
    GROUP BY technician_id, STRFTIME('%Y-%m', open_date)
),
tech_stats AS (
    SELECT
        technician_id,
        ROUND(AVG(wo_count), 1)                       AS avg_monthly_wo,
        MAX(wo_count)                                  AS max_monthly_wo,
        MIN(wo_count)                                  AS min_monthly_wo,
        COUNT(DISTINCT month)                          AS active_months
    FROM monthly_workload
    GROUP BY technician_id
)
SELECT
    ts.technician_id,
    ts.avg_monthly_wo,
    ts.max_monthly_wo,
    ts.min_monthly_wo,
    ts.active_months,
    ts.max_monthly_wo - ts.min_monthly_wo AS workload_range,
    CASE
        WHEN ts.max_monthly_wo > 2 * ts.avg_monthly_wo THEN 'UNEVEN'
        ELSE 'BALANCED'
    END AS distribution_flag
FROM tech_stats ts
ORDER BY workload_range DESC;
