-- Query 3: Extreme Orders (Window Function Version)
-- For every user, finds their very first order and their very last order in a single query result.
-- Do not use self-joins. Uses FIRST_VALUE and LAST_VALUE over partitioned sets.

WITH ordered AS (
    SELECT
        user_id,
        FIRST_VALUE(created_at) OVER (
            PARTITION BY user_id 
            ORDER BY created_at ASC, order_id ASC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS first_order_date,
        LAST_VALUE(created_at) OVER (
            PARTITION BY user_id 
            ORDER BY created_at ASC, order_id ASC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_order_date,
        FIRST_VALUE(amount) OVER (
            PARTITION BY user_id 
            ORDER BY created_at ASC, order_id ASC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS first_order_amount,
        LAST_VALUE(amount) OVER (
            PARTITION BY user_id 
            ORDER BY created_at ASC, order_id ASC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_order_amount,
        ROW_NUMBER() OVER (
            PARTITION BY user_id 
            ORDER BY created_at ASC, order_id ASC
        ) AS rn
    FROM orders
)
SELECT 
    user_id, 
    first_order_date, 
    last_order_date, 
    first_order_amount, 
    last_order_amount
FROM ordered
WHERE rn = 1
ORDER BY user_id;
