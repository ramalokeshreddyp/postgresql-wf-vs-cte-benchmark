-- Recursive Referral Chains
-- Finds the complete referral chain depth for the top 100 users by order count.
-- Traverses the parent-child relationships where users.referred_by = parent.user_id.
-- A user who hasn't referred anyone else will have a minimum depth of 1.

WITH RECURSIVE top_100 AS (
    -- Top 100 users by order count
    SELECT user_id
    FROM orders
    GROUP BY user_id
    ORDER BY COUNT(*) DESC
    LIMIT 100
),
referrals AS (
    -- Anchor member: Start with each of the top 100 users
    SELECT
        t.user_id AS root_user_id,
        u.user_id AS current_user_id,
        1 AS depth
    FROM top_100 t
    JOIN users u ON u.user_id = t.user_id

    UNION ALL

    -- Recursive member: Find users referred by the current set of users
    SELECT
        r.root_user_id,
        u.user_id AS current_user_id,
        r.depth + 1 AS depth
    FROM referrals r
    JOIN users u ON u.referred_by = r.current_user_id
)
SELECT
    root_user_id AS user_id,
    MAX(depth) AS chain_depth
FROM referrals
GROUP BY root_user_id
ORDER BY chain_depth DESC, root_user_id ASC;
