-- Mean Time Between Replacement (MTBR)
-- For each part, calculate actual mean flight hours between consecutive
-- replacements using LAG() window function, compared against catalog MTBF.
-- Demonstrates: LAG() window function, CTE, JOIN across 3+ tables.

WITH ordered_replacements AS (
    SELECT
        pr.part_id,
        wo.engine_id,
        pr.flight_hours_at_replacement,
        LAG(pr.flight_hours_at_replacement) OVER (
            PARTITION BY pr.part_id, wo.engine_id
            ORDER BY pr.flight_hours_at_replacement
        ) AS prev_replacement_hours
    FROM part_replacements pr
    JOIN work_orders wo ON pr.work_order_id = wo.work_order_id
),
intervals AS (
    SELECT
        part_id,
        engine_id,
        flight_hours_at_replacement - prev_replacement_hours AS hours_between
    FROM ordered_replacements
    WHERE prev_replacement_hours IS NOT NULL
      AND flight_hours_at_replacement > prev_replacement_hours
)
SELECT
    p.part_id,
    p.part_name,
    p.mean_time_between_failure_hours AS catalog_mtbf,
    ROUND(AVG(i.hours_between), 1)    AS actual_mtbr,
    COUNT(i.hours_between)            AS interval_count,
    ROUND(AVG(i.hours_between) - p.mean_time_between_failure_hours, 1) AS mtbr_vs_mtbf_delta
FROM parts p
LEFT JOIN intervals i ON p.part_id = i.part_id
GROUP BY p.part_id, p.part_name, p.mean_time_between_failure_hours
ORDER BY mtbr_vs_mtbf_delta ASC;
