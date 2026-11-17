# Runbook RB-04: Data Ingestion Failure

**Category:** Data Ingestion Failure
**Typical symptoms:** ingestion error rate spike, malformed record spike, source connection failures
**First response target:** 15 minutes from alert

## 1. Confirm the problem

1. Identify the failing connector or source from the ingestion error stream; group errors by source and by error type before touching anything.
2. Check whether the failure is total (no records landing) or partial (a rising rejection rate). The fix path differs.

## 2. Diagnose

1. Sample rejected records and compare them field by field against the registered schema. A new or renamed field means the upstream schema changed without notice.
2. Check source connectivity: connection pool usage on the source database, failed login attempts, and network path. Pool exhaustion shows as timeouts that grow through the day.
3. For file-based feeds, check the delivery manifest and a sample file. Corrupted partner batches usually fail on a consistent byte pattern or encoding.
4. Check connector task state. A task in a failed state that never restarted is the simplest cause and the easiest to miss.

## 3. Fix

1. Pause the failing connector to stop error amplification and protect downstream consumers from partial data.
2. Restart a failed connector task; reset an exhausted source connection pool or raise its limit with the source owner's approval.
3. Quarantine malformed records to the dead letter queue with the rejection reason attached. Never drop them silently.
4. Apply the schema mapping fix for changed upstream fields, in coordination with the source owner, and register the new schema version.
5. Resume ingestion at a reduced rate, watch the rejection rate, then restore full rate.
6. Backfill the gap window from the source and reconcile record counts between source and platform before closing.

## 4. Verify

1. Ingestion error rate back below 0.5% for 30 minutes.
2. Record counts reconciled for the whole gap window.
3. Dead letter queue contents triaged with an owner and a replay or discard decision each.

## 5. Escalate when

- The source system is owned by another team and is down on their side.
- Corrupted data has already reached downstream consumers. Escalate to the data governance contact and notify consumers before backfilling.

## 6. Prevention

- Contract tests on upstream schemas in the deployment pipeline.
- Connector task auto-restart with alerting on restart count.
- Dead letter queue depth as a standing dashboard metric, reviewed daily.
