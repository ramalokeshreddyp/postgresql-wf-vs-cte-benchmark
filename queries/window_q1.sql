-- Query 1: Rolling Revenue (Window Function Version)
-- Calculates the 7-day rolling average revenue per calendar day for the last 90 days.
-- To ensure the rolling average for the first day of the last 90 days is calculated correctly,
-- we generate daily revenues starting from 96 days ago, compute the rolling average,
-- and then filter the final result set to the last 90 days.

WITH daily_rev AS (
    SELECT
        d.day::date AS day,
        COALESCE(SUM(o.amount), 0) AS daily_revenue
    FROM generate_series(
        CURRENT_DATE - INTERVAL '96 days',
        CURRENT_DATE,
        INTERVAL '1 day'
    ) d(day)
    LEFT JOIN orders o ON o.created_at::date = d.day::date
    GROUP BY d.day
),
rolling AS (
    SELECT
        day,
        daily_revenue,
        AVG(daily_revenue) OVER (
            ORDER BY day
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg
    FROM daily_rev
)
SELECT 
    day, 
    daily_revenue, 
    ROUND(rolling_7d_avg, 2) AS rolling_7d_avg
FROM rolling
WHERE day >= CURRENT_DATE - INTERVAL '89 days'
ORDER BY day;
