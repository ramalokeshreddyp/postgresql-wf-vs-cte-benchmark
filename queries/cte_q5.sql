-- Query 5: Revenue Contribution (CTE Version)
-- For every order, calculate its percentage contribution to that user's lifetime total spend.
-- Avoids window functions by grouping and summing amounts per user in a CTE, then joining it back.

WITH user_totals AS (
    SELECT
        user_id,
        SUM(amount) AS total_spend
    FROM orders
    GROUP BY user_id
)
SELECT
    o.order_id,
    o.user_id,
    o.amount,
    ROUND((o.amount / ut.total_spend) * 100, 4) AS lifetime_share_pct
FROM orders o
JOIN user_totals ut ON o.user_id = ut.user_id
ORDER BY o.user_id, o.order_id;
