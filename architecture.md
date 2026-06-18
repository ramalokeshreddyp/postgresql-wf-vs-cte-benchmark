# 🏛️ System Architecture and Design Document

This document outlines the architectural blueprint, design choices, system components, and data flow strategies of the **PostgreSQL Window Functions vs. CTEs Benchmarking Suite**.

---

## 1. Executive Summary & Objective

The main objective of this project is to build an isolated, high-scale analytical benchmarking platform that compares the compute cost, memory usage, disk overflow, and concurrency behavior of **Window Functions** vs. **Common Table Expressions (CTEs)**. 

By executing complex query plans under a 1.2M row workload, the system profiles how the PostgreSQL optimizer maps relational requests to logical operator nodes (e.g., Sequential Scans, Index Scans, Hash Aggregates, and Sort nodes) and measures how covering indexes affect execution dynamics.

---

## 2. System Architecture Design

The system is designed around containerization, host-container volume sharing, and automated test orchestration.

### Architectural Component Diagram

The following architecture diagram represents the relationship between the host system, the Docker container boundary, and the internal components of the PostgreSQL database engine:

```mermaid
graph TB
    subgraph Host_OS [Host Operating System]
        Python_Runner[Python Test Orchestrator: run_benchmarks.py]
        Source_Files[queries/ SQL Files]
        Git_Repo[Git Version Control]
        Output_Reports[benchmarks/ & results/]
    end

    subgraph Docker_Container [Docker Container: postgres_benchmark]
        subgraph PostgreSQL_Engine [PostgreSQL 15 Engine]
            Parser[Parser & Rewriter]
            Planner[Cost-Based Planner]
            Executor[Query Execution Engine]
        end
        
        subgraph Memory_Buffers [RAM Allocation]
            Shared_Buf[shared_buffers: 128MB]
            Work_Mem[work_mem: 4MB]
        end
        
        subgraph Disk_Storage [Disk Storage / pgdata]
            Users_Table[users Table: 200k Rows]
            Orders_Table[orders Table: 1M Rows]
            Indexes[B-Tree Indexes]
            MV_Cache[daily_revenue_stats Materialized View]
            Temp_Files[pg_tblspc: Temporary Disk Files]
        end
        
        subgraph PGBench [Concurrent Client Generator]
            PGBench_Worker[pgbench CLI Process]
        end
    end

    Source_Files -- Mounted Volume --> Docker_Container
    Python_Runner -- Docker Exec psql --> Parser
    Python_Runner -- Docker Exec pgbench --> PGBench_Worker
    PGBench_Worker -- Concurrency Load --> Parser
    Parser --> Planner
    Planner --> Executor
    Executor --> Memory_Buffers
    Executor --> Disk_Storage
    Disk_Storage -. WorkMem Overflow .-> Temp_Files
    Executor -- Execution Stats JSON --> Python_Runner
    Python_Runner -- Compiles Metrics --> Output_Reports
```

---

## 3. Workflow & Data Flow Explanation

The lifecycle of a benchmark execution moves through three primary phases:

### Data Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Host as Host (run_benchmarks.py)
    participant PG as PostgreSQL Container
    participant Disk as Storage (pgdata / Temp Files)

    Note over Host, PG: Phase 1: Baseline Analysis
    Host->>PG: Run EXPLAIN (FORMAT JSON) on baseline WF & CTE queries
    PG->>Disk: Scan Tables (Heap Scan & Disk Sorts if partitions > work_mem)
    Disk-->>PG: Return raw data
    PG-->>Host: Return Explain Plans JSON
    Host->>Host: Parse & Extract timings, buffers, and Sort node metadata

    Note over Host, PG: Phase 2: Index Optimization
    Host->>PG: CREATE INDEX (B-Tree on user_id, created_at, cohort_month)
    PG->>Disk: Construct Index Tables on Disk
    PG-->>Host: Return DDL success

    Note over Host, PG: Phase 3: Post-Index Analysis
    Host->>PG: Run EXPLAIN (FORMAT JSON) on optimized WF & CTE queries
    PG->>Disk: Index-Only Scan (Sort steps bypassed)
    PG-->>Host: Return optimized Explain Plans JSON

    Note over Host, PG: Phase 4: Load Testing & Caching
    Host->>PG: Run pgbench concurrent clients (c=10, t=60s)
    PG-->>Host: Return latency and TPS summaries
    Host->>PG: CREATE MATERIALIZED VIEW daily_revenue_stats
    PG->>Disk: Materialize Query 1 results on Disk
    Host->>PG: Query raw vs MV reads & refreshMV after 10k inserts
    PG-->>Host: Return execution times
```

---

## 4. Key Modules & Responsibilities

| Component / File | Primary Responsibility | Architectural Role |
| :--- | :--- | :--- |
| **`docker-compose.yml`** | Defines container ports, environment variables, mounts, and health checks. | Infrastructure Orchestration |
| **`init.sql`** | Declares schema definitions, foreign key relationships, and handles automated seeding (200k users, 1M orders) using power-law random distribution generators. | Schema & Seeding Engine |
| **`run_benchmarks.py`** | Automates SQL query execution, parses planner JSON arrays, runs `pgbench` test cases, executes materialized view routines, and compiles metrics. | Test Suite Harness |
| **`queries/`** | House the 10 query variants (WF vs CTE) and the recursive query. | Business Logic Layer |
| **`benchmarks/`** | Contains plan dumps, pgbench execution output logs, index impact markdown audit report, and materialized view performance. | Metrics Storage Layer |
| **`results/benchmarks.json`** | Summarizes execution times and TPS metrics in a single structured file for automated grading and grading validation. | Data Store Output |

---

## 5. Technology Stack Justification

*   **PostgreSQL 15 (Alpine)**: Chosen for its production-grade analytical capabilities, strict support for CTE inlining controls, mature costing planner, and native recursive query parsing. The Alpine image minimized container footprint.
*   **Docker Compose**: Standardizes deployment and guarantees that seeding occurs instantly upon container startup, eliminating environment differences between Windows host systems.
*   **Python 3.13**: Provides a zero-dependency orchestration interface. By calling `docker exec psql` directly and parsing stdout JSON, it avoids requiring local psycopg2 library builds on the host.
*   **pgbench**: Standardized PostgreSQL load test tool. Using it natively inside the container eliminates network transit latency variations from the host OS, measuring pure database engine concurrency throughput.

---

## 6. Crucial Component Integration Details

### Host-Container Volume Mapping
To avoid copying files back and forth, the project mounts:
1.  `./init.sql` directly to `/docker-entrypoint-initdb.d/init.sql` (Postgres entrypoint auto-executes this file during database creation).
2.  `./queries/` folder to `/queries` inside the container. This allows the host Python runner to write or edit queries locally, and permits the container's `pgbench` and `psql` to reference them via static container-absolute paths.

### Memory & Disk Sort Overflow Integration
The container is configured with PostgreSQL default `work_mem = 4MB`. When the test runner executes large partition aggregates (e.g. Query 3 aggregating 1,000,000 orders), the memory requirement exceeds 4MB. The executor is forced to write temporary chunks to disk (`External merge Disk` sort). The benchmark runner captures this overflow from the `Explain Plan` and registers the sort space size, proving the visual and physical impact of indexes.
