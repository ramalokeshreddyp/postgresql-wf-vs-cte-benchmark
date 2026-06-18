-- Query 4: Customer Churn Risk (Window Function Version)
-- Identify users who are 'At Risk'. A user is at risk if their order count in the last 30 days
-- is lower than their order count in the 30-day period prior to that (previous 30 days).
-- The Window Function version uses LAG() to compare counts across these two periods.

WITH periods AS (
    SELECT 1 AS period
    UNION ALL
    SELECT 2 AS period
),
user_active AS (
    SELECT DISTINCT user_id
    FROM orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '60 days'
),
user_periods AS (
    SELECT u.user_id, p.period
    FROM user_active u
    CROSS JOIN periods p
),
order_counts AS (
    SELECT
        user_id,
        CASE
            WHEN created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1
            ELSE 2
        END AS period,
        COUNT(*) AS cnt
    FROM orders
    WHERE created_at >= CURRENT_DATE - INTERVAL '60 days'
    GROUP BY user_id, period
),
combined AS (
    SELECT
        up.user_id,
        up.period,
        COALESCE(oc.cnt, 0) AS order_count
    FROM user_periods up
    LEFT JOIN order_counts oc ON up.user_id = oc.user_id AND up.period = oc.period
),
lagged AS (
    SELECT
        user_id,
        period,
        order_count,
        LAG(order_count) OVER (PARTITION BY user_id ORDER BY period DESC) AS prev_order_count
    FROM combined
)
SELECT
    user_id,
    order_count AS orders_last_30d,
    prev_order_count AS orders_prev_30d
FROM lagged
WHERE period = 1
  AND order_count < prev_order_count
ORDER BY user_id;
