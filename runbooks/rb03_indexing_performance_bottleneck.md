# Runbook RB-03: Indexing Performance Bottleneck

**Category:** Indexing Performance Bottleneck
**Typical symptoms:** indexing latency p95 high, indexing queue backlog growing, segment merge pressure high
**First response target:** 20 minutes from alert

## 1. Confirm the problem

1. Compare indexing latency p95 and queue depth against search latency. If search is healthy and indexing is not, the bottleneck is on the write path; do not restart search nodes.
2. Note the queue growth rate. A queue that grows faster than the drain rate during peak will not recover on its own.

## 2. Diagnose

1. Check segment counts per shard. Very high counts with heavy merge activity point at oversized bulk requests creating large unmerged segments.
2. Check the refresh interval on high-volume indices. An interval set aggressively low (for example 1 second on a firehose index) multiplies segment creation.
3. Check mapping growth. A rapidly rising field count indicates field explosion from unbounded dynamic mappings, often after a new producer starts sending free-form fields.
4. Review recent version upgrades for changed merge throttling defaults.

## 3. Fix

1. Reduce bulk request sizes at the producer or gateway and split oversized batches so segments stay in the target size range.
2. Raise the refresh interval on high-volume indices to the value agreed with the data consumers, then re-measure after one full refresh cycle.
3. Add explicit mappings for the new fields and switch the index to strict or controlled dynamic mapping to stop field explosion.
4. Restore merge throttling values from the pre-upgrade configuration if an upgrade changed them.
5. Force a merge only in a low-traffic window and only when segment counts are extreme; a force merge during peak makes latency worse.

## 4. Verify

1. Indexing latency p95 back under the service target for one full hour.
2. Queue depth draining and staying near zero through a normal traffic peak.
3. Segment counts per shard stable or falling.

## 5. Escalate when

- Latency stays high after bulk size, refresh, and mapping fixes are applied.
- The backlog threatens the retention window of the ingestion queue. Escalate to the search platform team with segment and mapping evidence.

## 6. Prevention

- Load test indexing with production-shaped bulk sizes, not small synthetic batches.
- Review field counts weekly; alert on growth rate, not just totals.
- Pin merge and refresh settings in configuration management so upgrades cannot silently change them.
