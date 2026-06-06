-- Cost Per Flight Hour by Engine Model
-- Total maintenance cost divided by total flight hours, ranked across models.
-- Demonstrates: JOIN across 3+ tables, aggregate functions, window function RANK().

SELECT
    e.engine_model,
    ROUND(SUM(e_hours.total_flight_hours), 0) AS total_fleet_hours,
    ROUND(SUM(costs.total_cost), 2)           AS total_maintenance_cost,
    ROUND(SUM(costs.total_cost) / SUM(e_hours.total_flight_hours), 2) AS cost_per_flight_hour,
    RANK() OVER (
        ORDER BY SUM(costs.total_cost) / SUM(e_hours.total_flight_hours) DESC
    ) AS cost_rank
FROM engines e
JOIN (
    SELECT engine_id, total_flight_hours
    FROM engines
) e_hours ON e.engine_id = e_hours.engine_id
LEFT JOIN (
    SELECT
        wo.engine_id,
        SUM(pr.quantity * p.unit_cost_usd) AS total_cost
    FROM work_orders wo
    JOIN part_replacements pr ON wo.work_order_id = pr.work_order_id
    JOIN parts p ON pr.part_id = p.part_id
    GROUP BY wo.engine_id
) costs ON e.engine_id = costs.engine_id
GROUP BY e.engine_model
ORDER BY cost_per_flight_hour DESC;
