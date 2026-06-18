-- Query 4: Customer Churn Risk (CTE Version)
-- Identify users who are 'At Risk'. A user is at risk if their order count in the last 30 days
-- is lower than their order count in the 30-day period prior to that.
-- CTE version calculates two separate temporal buckets in CTEs and joins them together.

WITH last_30d AS (
    SELECT user_id, COUNT(*) AS orders_last_30d
    FROM orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
),
prev_30d AS (
    SELECT user_id, COUNT(*) AS orders_prev_30d
    FROM orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '60 days'
      AND created_at < CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
),
all_users AS (
    SELECT DISTINCT user_id
    FROM orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '60 days'
)
SELECT
    au.user_id,
    COALESCE(l.orders_last_30d, 0) AS orders_last_30d,
    COALESCE(p.orders_prev_30d, 0) AS orders_prev_30d
FROM all_users au
LEFT JOIN last_30d l ON au.user_id = l.user_id
LEFT JOIN prev_30d p ON au.user_id = p.user_id
WHERE COALESCE(l.orders_last_30d, 0) < COALESCE(p.orders_prev_30d, 0)
ORDER BY au.user_id;
