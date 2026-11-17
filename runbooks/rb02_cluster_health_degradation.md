# Runbook RB-02: Cluster Health Degradation

**Category:** Cluster Health Degradation
**Typical symptoms:** broker CPU sustained high, broker memory pressure, disk usage near capacity, cluster node unresponsive
**First response target:** 10 minutes from alert

## 1. Confirm the problem

1. Query the cluster health endpoint and list node states. Identify whether one node or the whole cluster is degraded.
2. Record CPU, memory, disk, and JVM garbage collection pause times for the worst node before changing anything; this snapshot is the evidence for the root cause.

## 2. Diagnose

1. Disk near capacity: compare actual log segment retention on disk with the configured retention policy. A mismatch in units (hours configured where days were intended) is a known repeat offender.
2. Memory pressure with long GC pauses: check heap size against the node class standard and look for a recent change that reduced it.
3. Node unresponsive: check whether the process died, the host is unreachable, or the node is stuck in a long GC. Check whether its replicas were reassigned; under-replicated partitions that stay above zero mean reassignment stalled.
4. CPU saturation: list background jobs on the node (compaction, merges, backups) and check whether throttling settings were lost in an upgrade.

## 3. Fix

1. Cordon the degraded node from client traffic so clients fail over to healthy nodes.
2. Disk pressure: delete expired segments that are past the retention policy, or expand the volume. Never delete active segments.
3. Memory pressure: capture a heap dump, then restart the node process during the lowest traffic period available.
4. Failed node: reassign its replicas to healthy nodes and monitor the under-replicated partition count until it reaches zero.
5. CPU saturation: re-apply compaction throttling and reschedule background jobs outside peak hours.

## 4. Verify

1. All nodes report healthy status.
2. Under-replicated partitions at zero for 30 minutes.
3. Client error rates and produce latency back to baseline.

## 5. Escalate when

- Two or more nodes are degraded at once.
- Disk expansion or hardware replacement is needed. Escalate to infrastructure with the evidence snapshot attached.

## 6. Prevention

- Alert at 80% disk, not 95%; disk incidents are slow until they are sudden.
- Track GC pause time as a first-class cluster metric.
- Test replica reassignment in game days so a stalled reassignment is a known, rehearsed case.
