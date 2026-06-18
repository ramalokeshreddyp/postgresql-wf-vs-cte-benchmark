-- Query 5: Revenue Contribution (Window Function Version)
-- For every order, calculate its percentage contribution to that user's lifetime total spend.
-- The Window Function version uses SUM() OVER (PARTITION BY user_id) to reference the lifetime total.

SELECT
    order_id,
    user_id,
    amount,
    ROUND((amount / SUM(amount) OVER (PARTITION BY user_id)) * 100, 4) AS lifetime_share_pct
FROM orders
ORDER BY user_id, order_id;
