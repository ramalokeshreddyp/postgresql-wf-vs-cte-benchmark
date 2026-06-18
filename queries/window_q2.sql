-- Query 2: Cohort Spending Ranks (Window Function Version)
-- Rank users by their total lifetime spend within their signup-month cohort.
-- Returns the Top 10 spenders for every cohort.

WITH user_spend AS (
    SELECT
        u.cohort_month,
        u.user_id,
        SUM(o.amount) AS total_spend
    FROM users u
    JOIN orders o ON u.user_id = o.user_id
    GROUP BY u.cohort_month, u.user_id
),
ranked AS (
    SELECT
        cohort_month,
        user_id,
        total_spend,
        DENSE_RANK() OVER (PARTITION BY cohort_month ORDER BY total_spend DESC) AS rank_in_cohort
    FROM user_spend
)
SELECT 
    cohort_month, 
    user_id, 
    total_spend, 
    rank_in_cohort
FROM ranked
WHERE rank_in_cohort <= 10
ORDER BY cohort_month ASC, rank_in_cohort ASC, user_id ASC;
