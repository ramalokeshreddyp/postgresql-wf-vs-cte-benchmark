import os
import sys
import subprocess
import json
import time
import re

DB_USER = "postgres"
DB_NAME = "analytics_db"

def run_sql_command(sql, tuples_only=True):
    cmd = ["docker", "exec", "-i", "postgres_benchmark", "psql", "-U", DB_USER, "-d", DB_NAME]
    if tuples_only:
        cmd.extend(["-t", "-A"])
    cmd.extend(["-c", sql])
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise Exception(f"SQL command failed:\nCommand: {sql}\nError: {res.stderr}")
    return res.stdout.strip()

def run_sql_file(file_path, tuples_only=True):
    with open(file_path, 'r') as f:
        sql = f.read()
    # Strip single-line comments that start with --
    lines = []
    for line in sql.splitlines():
        if not line.strip().startswith('--'):
            lines.append(line)
    sql_clean = '\n'.join(lines)
    return run_sql_command(sql_clean, tuples_only)

def run_explain_analyze(file_path):
    with open(file_path, 'r') as f:
        sql = f.read()
    
    # Strip comments
    lines = []
    for line in sql.splitlines():
        if not line.strip().startswith('--'):
            lines.append(line)
    sql_clean = '\n'.join(lines)
    
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql_clean}"
    raw_json = run_sql_command(explain_sql, tuples_only=True)
    try:
        plan = json.loads(raw_json)
        return plan
    except Exception as e:
        print(f"Error parsing JSON for {file_path}: {e}")
        print(f"Raw output: {raw_json[:500]}")
        raise e

def find_sort_nodes(plan_node):
    sort_nodes = []
    if plan_node.get("Node Type") == "Sort":
        sort_nodes.append({
            "method": plan_node.get("Sort Method"),
            "space_used": plan_node.get("Sort Space Used"),
            "space_type": plan_node.get("Sort Space Type")
        })
    if "Plans" in plan_node:
        for subplan in plan_node["Plans"]:
            sort_nodes.extend(find_sort_nodes(subplan))
    return sort_nodes

def extract_metrics(plan_json):
    # EXPLAIN FORMAT JSON returns an array of plans
    plan = plan_json[0]["Plan"]
    exec_time = plan_json[0]["Execution Time"] # in ms
    plan_time = plan_json[0]["Planning Time"] # in ms
    
    # Extract buffer hits/reads
    shared_hit = plan.get("Shared Hit Blocks", 0)
    shared_read = plan.get("Shared Read Blocks", 0)
    shared_written = plan.get("Shared Written Blocks", 0)
    shared_dirtied = plan.get("Shared Dirtied Blocks", 0)
    
    # Extract sort details recursively
    sort_nodes = find_sort_nodes(plan)
    
    return {
        "execution_time_ms": exec_time,
        "planning_time_ms": plan_time,
        "shared_hit": shared_hit,
        "shared_read": shared_read,
        "shared_written": shared_written,
        "shared_dirtied": shared_dirtied,
        "sorts": sort_nodes
    }

def run_pgbench(file_name, clients=10, duration=60):
    container_path = f"/queries/{file_name}"
    cmd = [
        "docker", "exec", "-i", "postgres_benchmark",
        "pgbench", "-U", DB_USER, "-d", DB_NAME,
        "-c", str(clients), "-j", "2", "-T", str(duration),
        "-f", container_path
    ]
    print(f"Running pgbench for {file_name} with {clients} clients for {duration}s...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"pgbench failed for {file_name}: {res.stderr}")
        return None, None
    
    stdout = res.stdout
    # Parse latency average and tps
    latency = None
    tps = None
    
    lat_match = re.search(r"latency average = (\d+\.\d+) ms", stdout)
    tps_match = re.search(r"tps = (\d+\.\d+)", stdout)
    
    if lat_match:
        latency = float(lat_match.group(1))
    if tps_match:
        tps = float(tps_match.group(1))
        
    return tps, latency, stdout

def main():
    os.makedirs("benchmarks", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    
    queries = {
        "q1": {"wf": "window_q1.sql", "cte": "cte_q1.sql"},
        "q2": {"wf": "window_q2.sql", "cte": "cte_q2.sql"},
        "q3": {"wf": "window_q3.sql", "cte": "cte_q3.sql"},
        "q4": {"wf": "window_q4.sql", "cte": "cte_q4.sql"},
        "q5": {"wf": "window_q5.sql", "cte": "cte_q5.sql"}
    }
    
    # 1. Baseline analysis (before indexes)
    print("--- 1. Running Baseline Benchmarks (Before Indexes) ---")
    before_metrics = {}
    for q_key, variants in queries.items():
        before_metrics[q_key] = {}
        for style in ["wf", "cte"]:
            file_name = variants[style]
            file_path = os.path.join("queries", file_name)
            print(f"Explaining {file_name}...")
            plan = run_explain_analyze(file_path)
            
            # Save explain json to file
            with open(os.path.join("benchmarks", f"before_{file_name}.json"), "w") as out:
                json.dump(plan, out, indent=2)
                
            metrics = extract_metrics(plan)
            before_metrics[q_key][style] = metrics
            print(f"  Execution Time: {metrics['execution_time_ms']} ms | Sorts: {metrics['sorts']}")

    # 2. Index Optimization
    print("\n--- 2. Creating Indexes ---")
    print("Creating index idx_orders_user_created on orders(user_id, created_at)...")
    run_sql_command("CREATE INDEX idx_orders_user_created ON orders(user_id, created_at);")
    print("Creating index idx_users_cohort on users(cohort_month)...")
    run_sql_command("CREATE INDEX idx_users_cohort ON users(cohort_month);")

    # 3. Post-Index analysis
    print("\n--- 3. Running Post-Index Benchmarks ---")
    after_metrics = {}
    for q_key, variants in queries.items():
        after_metrics[q_key] = {}
        for style in ["wf", "cte"]:
            file_name = variants[style]
            file_path = os.path.join("queries", file_name)
            print(f"Explaining {file_name}...")
            plan = run_explain_analyze(file_path)
            
            # Save explain json to file
            with open(os.path.join("benchmarks", f"after_{file_name}.json"), "w") as out:
                json.dump(plan, out, indent=2)
                
            metrics = extract_metrics(plan)
            after_metrics[q_key][style] = metrics
            print(f"  Execution Time: {metrics['execution_time_ms']} ms | Sorts: {metrics['sorts']}")

    # 4. Concurrent Load Testing (pgbench)
    print("\n--- 4. Running pgbench Load Tests (60s each) ---")
    pgbench_results = {}
    for q_key in ["q1", "q2"]:
        pgbench_results[q_key] = {}
        for style in ["wf", "cte"]:
            file_name = queries[q_key][style]
            tps, latency, raw_out = run_pgbench(file_name, clients=10, duration=60)
            pgbench_results[q_key][style] = {"tps": tps, "latency_ms": latency}
            
            # Save pgbench raw output
            with open(os.path.join("benchmarks", f"pgbench_{file_name}.txt"), "w") as out:
                out.write(raw_out)
            print(f"  {file_name} pgbench -> TPS: {tps} | Latency: {latency} ms")

    # 5. Materialized View Strategy Benchmarking
    print("\n--- 5. Benchmarking Materialized View ---")
    # Drop materialized view if it already exists
    run_sql_command("DROP MATERIALIZED VIEW IF EXISTS daily_revenue_stats;")
    
    # Measure creation time
    print("Creating materialized view daily_revenue_stats...")
    start_create = time.time()
    # We will build the MV based on window_q1.sql
    with open("queries/window_q1.sql", "r") as f:
        q1_sql = f.read()
    # Strip comments
    q1_lines = [l for l in q1_sql.splitlines() if not l.strip().startswith('--')]
    q1_sql_clean = '\n'.join(q1_lines)
    create_mv_sql = f"CREATE MATERIALIZED VIEW daily_revenue_stats AS {q1_sql_clean}"
    run_sql_command(create_mv_sql)
    mv_create_time_ms = (time.time() - start_create) * 1000.0
    print(f"  Materialized View Creation Time: {mv_create_time_ms:.2f} ms")

    # Measure MV Read Time
    print("Measuring MV read time...")
    start_read = time.time()
    for _ in range(5):
        run_sql_command("SELECT * FROM daily_revenue_stats;", tuples_only=False)
    mv_read_time_ms = ((time.time() - start_read) / 5.0) * 1000.0
    print(f"  Materialized View Read Time (avg of 5 runs): {mv_read_time_ms:.2f} ms")

    # Measure Raw WF Read Time
    print("Measuring Raw Window Function read time...")
    start_raw = time.time()
    for _ in range(5):
        run_sql_file("queries/window_q1.sql", tuples_only=False)
    raw_read_time_ms = ((time.time() - start_raw) / 5.0) * 1000.0
    print(f"  Raw Window Function Read Time (avg of 5 runs): {raw_read_time_ms:.2f} ms")

    # Insert 10,000 new orders
    print("Inserting 10,000 new orders...")
    insert_sql = """
    INSERT INTO orders (order_id, user_id, product_id, amount, status, created_at, updated_at)
    SELECT
        gen_random_uuid() AS order_id,
        floor(1 + 200000 * power(random(), 3.5))::int AS user_id,
        floor(random() * 1000 + 1)::int AS product_id,
        (random() * 499 + 1)::numeric(10,2) AS amount,
        'completed' AS status,
        '2026-06-18 00:00:00'::timestamptz + (random() * interval '1 hour') AS created_at,
        '2026-06-18 00:00:00'::timestamptz + (random() * interval '1 hour') AS updated_at
    FROM generate_series(1, 10000) i;
    """
    run_sql_command(insert_sql)
    
    # Measure Refresh time
    print("Refreshing Materialized View...")
    start_refresh = time.time()
    run_sql_command("REFRESH MATERIALIZED VIEW daily_revenue_stats;")
    mv_refresh_time_ms = (time.time() - start_refresh) * 1000.0
    print(f"  Materialized View Refresh Time: {mv_refresh_time_ms:.2f} ms")

    # Write MV timings to a report log
    with open(os.path.join("benchmarks", "mv_performance.json"), "w") as out:
        json.dump({
            "mv_creation_time_ms": mv_create_time_ms,
            "mv_read_time_ms": mv_read_time_ms,
            "raw_read_time_ms": raw_read_time_ms,
            "mv_refresh_time_ms_after_10k_inserts": mv_refresh_time_ms
        }, out, indent=2)

    # 6. Generate results/benchmarks.json
    print("\n--- 6. Saving results/benchmarks.json ---")
    results = {
        "query_1": {
            "wf_ms": round(after_metrics["q1"]["wf"]["execution_time_ms"], 2),
            "cte_ms": round(after_metrics["q1"]["cte"]["execution_time_ms"], 2),
            "index_speedup": round(before_metrics["q1"]["wf"]["execution_time_ms"] / after_metrics["q1"]["wf"]["execution_time_ms"], 2)
        },
        "query_2": {
            "wf_ms": round(after_metrics["q2"]["wf"]["execution_time_ms"], 2),
            "cte_ms": round(after_metrics["q2"]["cte"]["execution_time_ms"], 2),
            "index_speedup": round(before_metrics["q2"]["wf"]["execution_time_ms"] / after_metrics["q2"]["wf"]["execution_time_ms"], 2)
        },
        "query_3": {
            "wf_ms": round(after_metrics["q3"]["wf"]["execution_time_ms"], 2),
            "cte_ms": round(after_metrics["q3"]["cte"]["execution_time_ms"], 2),
            "index_speedup": round(before_metrics["q3"]["wf"]["execution_time_ms"] / after_metrics["q3"]["wf"]["execution_time_ms"], 2)
        },
        "query_4": {
            "wf_ms": round(after_metrics["q4"]["wf"]["execution_time_ms"], 2),
            "cte_ms": round(after_metrics["q4"]["cte"]["execution_time_ms"], 2),
            "index_speedup": round(before_metrics["q4"]["wf"]["execution_time_ms"] / after_metrics["q4"]["wf"]["execution_time_ms"], 2)
        },
        "query_5": {
            "wf_ms": round(after_metrics["q5"]["wf"]["execution_time_ms"], 2),
            "cte_ms": round(after_metrics["q5"]["cte"]["execution_time_ms"], 2),
            "index_speedup": round(before_metrics["q5"]["wf"]["execution_time_ms"] / after_metrics["q5"]["wf"]["execution_time_ms"], 2)
        },
        "pgbench_results": {
            "wf_tps": pgbench_results["q1"]["wf"]["tps"],
            "cte_tps": pgbench_results["q1"]["cte"]["tps"],
            "q1_wf_tps": pgbench_results["q1"]["wf"]["tps"],
            "q1_cte_tps": pgbench_results["q1"]["cte"]["tps"],
            "q2_wf_tps": pgbench_results["q2"]["wf"]["tps"],
            "q2_cte_tps": pgbench_results["q2"]["cte"]["tps"]
        }
    }
    
    with open(os.path.join("results", "benchmarks.json"), "w") as out:
        json.dump(results, out, indent=2)
    print("Done! results/benchmarks.json written successfully.")

    # 7. Write index impact report for window Q1
    print("\n--- 7. Writing index impact report ---")
    report_content = f"""# Index Impact Report: Query 1 (Window Version)

This report verifies the impact of applying database indexes on the 7-day rolling revenue average query (Window Function version).

## Execution Timings
- **Execution Time Before Indexes**: {before_metrics["q1"]["wf"]["execution_time_ms"]:.2f} ms
- **Execution Time After Indexes**: {after_metrics["q1"]["wf"]["execution_time_ms"]:.2f} ms
- **Speedup Ratio**: {before_metrics["q1"]["wf"]["execution_time_ms"] / after_metrics["q1"]["wf"]["execution_time_ms"]:.2f}x

## Buffer and Sort Details

### Before Indexes
- **Shared Hit Blocks**: {before_metrics["q1"]["wf"]["shared_hit"]}
- **Shared Read Blocks**: {before_metrics["q1"]["wf"]["shared_read"]}
- **Shared Written Blocks**: {before_metrics["q1"]["wf"]["shared_written"]}
- **Shared Dirtied Blocks**: {before_metrics["q1"]["wf"]["shared_dirtied"]}
- **Sort Nodes**: {before_metrics["q1"]["wf"]["sorts"]}

### After Indexes
- **Shared Hit Blocks**: {after_metrics["q1"]["wf"]["shared_hit"]}
- **Shared Read Blocks**: {after_metrics["q1"]["wf"]["shared_read"]}
- **Shared Written Blocks**: {after_metrics["q1"]["wf"]["shared_written"]}
- **Shared Dirtied Blocks**: {after_metrics["q1"]["wf"]["shared_dirtied"]}
- **Sort Nodes**: {after_metrics["q1"]["wf"]["sorts"]}

## Explanation of Impact
Before indexes, PostgreSQL had to perform a full sequential scan on the `orders` table to aggregate revenue per day.
After creating the composite B-Tree index on `orders(user_id, created_at)` and cohort indexes, the query optimizer can leverage index-only scans or index scans, and bypass or optimize sort steps because the rows are fetched in pre-sorted order.
"""
    with open(os.path.join("benchmarks", "index_impact_report.md"), "w") as out:
        out.write(report_content)
    print("Done! benchmarks/index_impact_report.md written.")

if __name__ == "__main__":
    main()
