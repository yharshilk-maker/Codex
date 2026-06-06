-- Fleet Status Summary
-- Count of engines by status and fleet type, with average flight hours per group.
-- Demonstrates: GROUP BY, aggregate functions, multi-dimension grouping.

SELECT
    fleet,
    status,
    COUNT(*)                        AS engine_count,
    ROUND(AVG(total_flight_hours), 1) AS avg_flight_hours,
    ROUND(MIN(total_flight_hours), 1) AS min_flight_hours,
    ROUND(MAX(total_flight_hours), 1) AS max_flight_hours
FROM engines
GROUP BY fleet, status
ORDER BY fleet, status;
