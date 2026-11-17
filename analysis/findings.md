# StreamGuard Findings

All figures below are computed from the synthetic incident dataset in
`data/incidents.csv` by `analysis/run_analysis.py`. The dataset is a
simulation modeled on typical streaming data platform behavior; it is
not production data from any company.

## Headline numbers

- Total incidents in the 90 day window (2026-01-01 09:07 to 2026-03-31 12:23): **384**
- Overall mean time to resolve (MTTR): **157.77 minutes** (median 124.0 minutes)
- Mean CSAT: **4.75 out of 5**, with 83.85% of incidents rated 5
- Escalation rate: **24.48%** (94 of 384 incidents)

## Category breakdown

| Category | Incidents | Share | MTTR (min) | Median (min) | CSAT mean | Escalation rate |
|---|---|---|---|---|---|---|
| Streaming Pipeline Failure | 110 | 28.65% | 111.77 | 96.0 | 4.81 | 22.73% |
| Cluster Health Degradation | 75 | 19.53% | 269.0 | 239 | 4.75 | 28.0% |
| Indexing Performance Bottleneck | 70 | 18.23% | 173.6 | 146.0 | 4.59 | 18.57% |
| Data Ingestion Failure | 89 | 23.18% | 147.9 | 125 | 4.73 | 25.84% |
| Configuration Error | 40 | 10.42% | 69.92 | 64.0 | 4.9 | 30.0% |

## What the numbers say

- Cluster Health Degradation is the slowest category to resolve at 269.0 minutes mean, well above Configuration Error at 69.92 minutes, which matches operational intuition: node and disk problems need physical or infrastructure action, while configuration errors end with a rollback.
- Streaming Pipeline Failure is the most frequent category with 110 incidents (28.65% of the total).
- Escalated incidents take much longer: 196.95 minutes mean versus 145.07 minutes for non-escalated ones, so escalation is a marker of genuinely hard incidents, not a shortcut.
- CSAT stays high but is resolution-time sensitive: incidents closed within 120 minutes average 4.81, while incidents taking over 300 minutes average 4.59.

## Recurring problems

14 root causes recur at least 15 times in the window and account for 83.33% of all incidents. The top recurring root causes:

- Consumer group rebalance storm caused by short session timeouts: 31 incidents
- Undersized partition count for the peak traffic profile: 30 incidents
- Broker leader election loop after a rolling restart: 30 incidents
- Connector task failed and did not restart automatically: 28 incidents
- JVM garbage collection pauses from an undersized heap: 26 incidents

These are the candidates for permanent fixes: each recurring root cause
that is engineered away removes its whole incident stream, which is a
larger MTTR win than handling individual incidents faster.

## Severity

| Severity | Incidents | MTTR (min) | Escalation rate |
|---|---|---|---|
| SEV1 | 31 | 297.23 | 48.39% |
| SEV2 | 120 | 178.13 | 40.0% |
| SEV3 | 154 | 141.52 | 18.83% |
| SEV4 | 79 | 103.77 | 2.53% |

## Charts

- charts/incidents_by_category.png
- charts/mttr_by_category.png
- charts/volume_trend_weekly.png
- charts/csat_distribution.png
- charts/mttr_by_severity.png
