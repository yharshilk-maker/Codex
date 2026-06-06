-- Top 10 Costliest Parts
-- Parts ranked by total replacement cost across all work orders.
-- Demonstrates: JOIN, aggregate with GROUP BY, RANK() window function.

SELECT
    ranked.part_id,
    ranked.part_name,
    ranked.part_category,
    ranked.total_quantity_replaced,
    ranked.total_cost_usd,
    ranked.cost_rank
FROM (
    SELECT
        p.part_id,
        p.part_name,
        p.part_category,
        SUM(pr.quantity)                    AS total_quantity_replaced,
        ROUND(SUM(pr.quantity * p.unit_cost_usd), 2) AS total_cost_usd,
        RANK() OVER (ORDER BY SUM(pr.quantity * p.unit_cost_usd) DESC) AS cost_rank
    FROM parts p
    JOIN part_replacements pr ON p.part_id = pr.part_id
    GROUP BY p.part_id, p.part_name, p.part_category
) ranked
WHERE ranked.cost_rank <= 10
ORDER BY ranked.cost_rank;
