-- Enable pgcrypto if needed, though gen_random_uuid() is built-in for PG 13+
-- We don't need CREATE EXTENSION "pgcrypto";

-- Create Users Table
CREATE TABLE users (
    user_id INT PRIMARY KEY,
    email VARCHAR UNIQUE,
    cohort_month DATE NOT NULL,
    referred_by INT NULL REFERENCES users(user_id)
);

-- Create Orders Table
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    product_id INT NOT NULL,
    amount NUMERIC CHECK (amount > 0),
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Users (200,000 rows)
-- We insert users sequentially and calculate referred_by dynamically.
-- Because referred_by points to a smaller user_id (which was already inserted),
-- it satisfies the foreign key constraint.
INSERT INTO users (user_id, email, cohort_month, referred_by)
SELECT
    i AS user_id,
    'user_' || i || '@example.com' AS email,
    ('2026-06-01'::date - (floor(random() * 24) * interval '1 month'))::date AS cohort_month,
    CASE 
        WHEN i > 1 AND random() < 0.3 THEN floor(random() * (i - 1) + 1)::int
        ELSE NULL
    END AS referred_by
FROM generate_series(1, 200000) i;

-- Seed Orders (1,000,000 rows)
-- We use a power law distribution for user_id to simulate realistic user purchasing behavior.
-- We join with the users table to ensure created_at is on or after the user's signup cohort.
INSERT INTO orders (order_id, user_id, product_id, amount, status, created_at, updated_at)
SELECT
    gen_random_uuid() AS order_id,
    s.u_id AS user_id,
    floor(random() * 1000 + 1)::int AS product_id,
    (random() * 499 + 1)::numeric(10,2) AS amount,
    (ARRAY['completed', 'completed', 'completed', 'pending', 'cancelled'])[floor(random() * 5 + 1)] AS status,
    u.cohort_month + (random() * (TIMESTAMP '2026-06-18 00:00:00' - u.cohort_month)) AS created_at,
    u.cohort_month + (random() * (TIMESTAMP '2026-06-18 00:00:00' - u.cohort_month)) + (random() * interval '1 hour') AS updated_at
FROM (
    SELECT floor(1 + 200000 * power(random(), 3.5))::int AS u_id
    FROM generate_series(1, 1000000) i
) s
JOIN users u ON u.user_id = s.u_id;
