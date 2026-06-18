# High-Performance SQL Analytics: Window Functions vs. CTEs in PostgreSQL

A comprehensive benchmarking suite in PostgreSQL 15+ to compare the performance, resource utilization, and execution plan characteristics of Window Functions (WFs) versus Common Table Expressions (CTEs) on a dataset of **1.2 million rows** (200,000 users and 1,000,000 orders).

---

## 📊 Benchmark Results

### 1. Query Execution Timings (Before vs. After Indexes)

*   **Index 1**: B-Tree composite index on `orders(user_id, created_at)`
*   **Index 2**: B-Tree index on `users(cohort_month)`

| Query | Style | Before Index (ms) | After Index (ms) | Speedup | Sort Details (Before ➡️ After) |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Q1: Rolling Revenue** | WF | 630.76 | 1023.76 | 0.62x | 2x Mem, 1x Disk ➡️ 2x Mem, 1x Disk |
| | CTE | 608.84 | 1173.35 | 0.52x | 2x Mem, 1x Disk ➡️ 2x Mem, 1x Disk |
| **Q2: Cohort Spending** | WF | 1412.05 | 945.29 | 1.49x | 1x Disk ➡️ 1x Disk |
| | CTE | 3585.90 | 3069.07 | 1.17x | 2x Mem ➡️ 2x Mem |
| **Q3: Extreme Orders** | WF | 2956.94 | 3093.92 | 0.96x | 1x Disk (48MB) ➡️ **None (Sorted by Index)** |
| | CTE | 1510.03 | 1509.37 | 1.00x | 1x Disk (48MB) ➡️ **None (Sorted by Index)** |
| **Q4: Churn Risk** | WF | 655.65 | 517.72 | 1.27x | 1x Disk ➡️ **None (Sorted by Index)** |
| | CTE | 474.75 | 251.54 | 1.89x | 1x Mem ➡️ **None (Sorted by Index)** |
| **Q5: Revenue Share** | WF | 1302.46 | 1416.79 | 0.92x | 1x Disk (36MB) ➡️ **None (Sorted by Index)** |
| | CTE | 1206.50 | 1723.25 | 0.70x | 2x Disk ➡️ 1x Disk |

### 2. Concurrent Load Test (`pgbench`)
Simulating **10 concurrent clients** running for **60 seconds**:

*   **Query 1 (Rolling Revenue)**:
    *   **Window Function**: **9.30 TPS** (Average Latency: **1075.60 ms**)
    *   **CTE**: **9.48 TPS** (Average Latency: **1055.24 ms**)
*   **Query 2 (Cohort Spending)**:
    *   **Window Function**: **8.12 TPS** (Average Latency: **1231.78 ms**)
    *   **CTE (Optimized Lateral)**: **2.93 TPS** (Average Latency: **3412.05 ms**)

---

## 🧠 Phase 4: The Recursive Challenge (Recursive vs. Window)

Window functions have a fundamental limitation: they **cannot** traverse recursive graph-like relationships (such as the referral chain from `referred_by` pointing to `user_id`).

### The "Fixed Window" vs. "Variable Depth" Constraint

1.  **Fixed Window (WF)**: Window functions evaluate calculations over a partition of rows that is structurally **fixed** during query parsing. The partition and the frame (e.g., `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`) must be resolved sequentially. The database engine cannot dynamically change the window's boundary or traverse child-to-parent hierarchies based on values encountered *during* the scan.
2.  **Variable Depth (Recursive CTE)**: Graph traversal requires a query to traverse a path of unknown depth (e.g., User A referred B, B referred C, C referred D, and so on). A recursive CTE solves this by dividing the execution into an **Anchor Member** (initial state) and a **Recursive Member** (joining the previous iteration's results with the table). It repeats this cycle until no new rows are returned, dynamically building the path level-by-level. Because a window function is evaluated on a static result set, it cannot reference its own output in a self-referential loop to expand the depth dynamically.

---

## ⚡ Phase 5: Materialized View Strategy

When real-time queries over millions of records become too expensive for dashboard rendering, a **Materialized View** serves as a pre-computed cache.

### Performance Comparison

*   **Initial Creation Time**: **628.93 ms**
*   **Read Time (`SELECT * FROM daily_revenue_stats`)**: **143.66 ms**
*   **Raw Window Function Query Time**: **632.72 ms**
*   **MV Speedup**: **4.4x faster reads**
*   **Refresh Time (`REFRESH MATERIALIZED VIEW`) after 10k inserts**: **642.99 ms**

> [!NOTE]
> Materializing the rolling revenue query aggregates the data physical onto disk, reducing the read overhead from $O(N \log N)$ (sorting/aggregating 1M rows) to $O(M)$ where $M$ is the number of calendar days (90 rows).

---

## 🛠️ Project Structure

```
├── docker-compose.yml        # Multi-container service configuration
├── .env.example              # Database env variables template
├── init.sql                  # Database schema & 1.2M record power-law seeding script
├── run_benchmarks.py         # Automates EXPLAIN, indexing, load tests, and MV benchmarks
├── queries/                  # 11 reporting queries (Window, CTE, and Recursive)
│   ├── window_q1.sql -> window_q5.sql
│   ├── cte_q1.sql -> cte_q5.sql
│   └── recursive_referrals.sql
├── benchmarks/               # Raw execution logs, plans, and reports
│   ├── before_*.json         # Plans before indexing
│   ├── after_*.json          # Plans after indexing
│   ├── pgbench_*.txt         # Raw pgbench load outputs
│   ├── mv_performance.json   # Materialized view timings
│   └── index_impact_report.md# Index impact audit
└── results/
    └── benchmarks.json       # Parsed metrics database file
```

---

## 🚀 How to Run the Benchmarks

### 1. Spin up the Database
Make sure Docker is running on your machine, then execute:
```bash
docker-compose up -d
```
*The database container will spin up and automatically execute `init.sql` to create the schema and seed 1.2 million rows (takes ~15-20 seconds).*

### 2. Run the Benchmarks Suite
Execute the python script to run all analysis and generate logs:
```bash
python run_benchmarks.py
```
*This will run baseline analysis, create indexes, run post-index analysis, trigger the pgbench concurrency load tests, benchmark the Materialized View, and populate the `results/benchmarks.json`.*
