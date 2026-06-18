-- Query 1: Rolling Revenue (CTE Version)
-- Calculates the 7-day rolling average revenue per calendar day for the last 90 days.
-- Avoids window functions by using a correlated subquery to average the daily revenues over the 7-day window.

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
        r.day,
        r.daily_revenue,
        (
            SELECT AVG(p.daily_revenue)
            FROM daily_rev p
            WHERE p.day BETWEEN r.day - 6 AND r.day
        ) AS rolling_7d_avg
    FROM daily_rev r
    WHERE r.day >= CURRENT_DATE - INTERVAL '89 days'
)
SELECT 
    day, 
    daily_revenue, 
    ROUND(rolling_7d_avg, 2) AS rolling_7d_avg
FROM rolling
ORDER BY day;
