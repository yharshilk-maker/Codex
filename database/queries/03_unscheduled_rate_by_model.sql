-- Unscheduled Maintenance Rate by Engine Model
-- Ratio of unscheduled to total work orders per engine model,
-- flagging models above 30%.
-- Demonstrates: JOIN, GROUP BY, HAVING, CASE expression.

SELECT
    e.engine_model,
    COUNT(*)                                                    AS total_work_orders,
    SUM(CASE WHEN wo.event_type = 'Unscheduled' THEN 1 ELSE 0 END) AS unscheduled_count,
    ROUND(
        100.0 * SUM(CASE WHEN wo.event_type = 'Unscheduled' THEN 1 ELSE 0 END) / COUNT(*),
        1
    )                                                           AS unscheduled_pct,
    CASE
        WHEN 100.0 * SUM(CASE WHEN wo.event_type = 'Unscheduled' THEN 1 ELSE 0 END) / COUNT(*) > 30
        THEN 'FLAGGED'
        ELSE 'OK'
    END                                                         AS flag
FROM work_orders wo
JOIN engines e ON wo.engine_id = e.engine_id
GROUP BY e.engine_model
ORDER BY unscheduled_pct DESC;
