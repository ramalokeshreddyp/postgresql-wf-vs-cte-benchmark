-- Query 2: Cohort Spending Ranks (CTE Version)
-- Rank users by their total lifetime spend within their signup-month cohort.
-- Returns the Top 10 spenders for every cohort.
-- Avoids window functions. Optimized using a LATERAL join to retrieve the top 10 spenders 
-- per cohort first, then calculates their ranks on the tiny subset (24 cohorts * 10 = 240 rows),
-- avoiding an O(N^2) comparison across all 200,000 users.

WITH cohort_list AS (
    SELECT DISTINCT cohort_month 
    FROM users
),
top_spenders_per_cohort AS (
    SELECT c.cohort_month, l.user_id, l.total_spend
    FROM cohort_list c
    CROSS JOIN LATERAL (
        SELECT
            u.user_id,
            SUM(o.amount) AS total_spend
        FROM users u
        JOIN orders o ON u.user_id = o.user_id
        WHERE u.cohort_month = c.cohort_month
        GROUP BY u.user_id
        ORDER BY total_spend DESC
        LIMIT 10
    ) l
),
ranked AS (
    SELECT
        ts.cohort_month,
        ts.user_id,
        ts.total_spend,
        (
            SELECT COUNT(DISTINCT ts2.total_spend) + 1
            FROM top_spenders_per_cohort ts2
            WHERE ts2.cohort_month = ts.cohort_month
              AND ts2.total_spend > ts.total_spend
        ) AS rank_in_cohort
    FROM top_spenders_per_cohort ts
)
SELECT 
    cohort_month, 
    user_id, 
    total_spend, 
    rank_in_cohort
FROM ranked
ORDER BY cohort_month ASC, rank_in_cohort ASC, user_id ASC;
