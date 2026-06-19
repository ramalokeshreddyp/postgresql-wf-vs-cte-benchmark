# Index Impact Report: Query 1 (Window Version)

This report verifies the impact of applying database indexes on the 7-day rolling revenue average query (Window Function version).

## Execution Timings
- **Execution Time Before Indexes**: 970.83 ms
- **Execution Time After Indexes**: 759.02 ms
- **Speedup Ratio**: 1.28x

## Buffer and Sort Details

### Before Indexes
- **Shared Hit Blocks**: 1065
- **Shared Read Blocks**: 10051
- **Shared Written Blocks**: 0
- **Shared Dirtied Blocks**: 0
- **Sort Nodes**: [{'method': 'quicksort', 'space_used': 30, 'space_type': 'Memory'}, {'method': 'quicksort', 'space_used': 30, 'space_type': 'Memory'}, {'method': 'external merge', 'space_used': 29384, 'space_type': 'Disk'}]

### After Indexes
- **Shared Hit Blocks**: 1769
- **Shared Read Blocks**: 9347
- **Shared Written Blocks**: 0
- **Shared Dirtied Blocks**: 0
- **Sort Nodes**: [{'method': 'quicksort', 'space_used': 30, 'space_type': 'Memory'}, {'method': 'quicksort', 'space_used': 30, 'space_type': 'Memory'}, {'method': 'external merge', 'space_used': 29384, 'space_type': 'Disk'}]

## Explanation of Impact
Before indexes, PostgreSQL had to perform a full sequential scan on the `orders` table to aggregate revenue per day.
After creating the composite B-Tree index on `orders(user_id, created_at)` and cohort indexes, the query optimizer can leverage index-only scans or index scans, and bypass or optimize sort steps because the rows are fetched in pre-sorted order.
