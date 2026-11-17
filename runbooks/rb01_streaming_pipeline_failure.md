# Runbook RB-01: Streaming Pipeline Failure

**Category:** Streaming Pipeline Failure
**Typical symptoms:** throughput drop, consumer lag spike, producer send error spike
**First response target:** 15 minutes from alert

## 1. Confirm the problem

1. Open the pipeline dashboard and compare current throughput (events/sec) with the same hour yesterday. A drop of 30% or more confirms a real event, not a traffic dip.
2. Check consumer lag per topic and partition. Note whether lag is uniform or concentrated on specific partitions.
3. Check the producer error rate. Errors concentrated on one topic point at that topic's partitions; errors everywhere point at the brokers.

## 2. Diagnose

1. Look at broker leader distribution. A leader election loop after a rolling restart shows up as repeated leader changes in the broker log.
2. Check consumer group state. Frequent rebalances in the group log, paired with lag that grows in steps, indicate a rebalance storm, usually from session timeouts that are too short for the processing time.
3. Check network saturation on the replication path (broker network throughput near link capacity) and under-replicated partitions.
4. Compare partition count against peak throughput per partition. Sustained per-partition saturation means the topic is undersized for its traffic profile.

## 3. Fix

1. Pause non-critical consumers on the affected topic to protect the critical path.
2. Restart the affected consumer group with an increased session timeout and a longer max poll interval if rebalancing is the driver.
3. Trigger a preferred replica election to restore balanced leadership, then watch replication lag return to zero.
4. If the topic is undersized, raise the partition count during the next maintenance window; partitions cannot be reduced later, so size for peak plus headroom.
5. Reprocess messages that aged past retention during the outage from the source system and reconcile counts end to end.

## 4. Verify

1. Throughput back within 10% of the expected baseline for the hour.
2. Consumer lag draining steadily and below the alert threshold for 30 minutes.
3. Producer error rate back below 0.2%.

## 5. Escalate when

- Lag does not drain within 60 minutes of the fix.
- More than one cluster is affected at the same time.
- Data loss is confirmed (messages past retention with no source replay path). Escalate to the platform engineering on-call and open a SEV1 bridge.

## 6. Prevention

- Alert on rebalance rate, not only on lag, so storms are caught early.
- Load test consumer groups with production-like processing times before raising throughput.
- Keep partition counts reviewed quarterly against traffic growth.
