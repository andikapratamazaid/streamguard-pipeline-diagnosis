"""Shared definitions for the StreamGuard simulation.

This module holds the symptom vocabulary, the five incident categories, the
symptom signature used to generate incidents, the root causes per category,
and the standard resolution steps. The incident generator, the telemetry
simulator, the diagnosis engine, and the tests all import from here so the
whole project speaks the same language.

All data in this project is synthetic. See README.md.
"""

# ---------------------------------------------------------------------------
# Incident categories (exact labels used everywhere)
# ---------------------------------------------------------------------------
CAT_STREAMING = "Streaming Pipeline Failure"
CAT_CLUSTER = "Cluster Health Degradation"
CAT_INDEXING = "Indexing Performance Bottleneck"
CAT_INGESTION = "Data Ingestion Failure"
CAT_CONFIG = "Configuration Error"

CATEGORIES = [CAT_STREAMING, CAT_CLUSTER, CAT_INDEXING, CAT_INGESTION, CAT_CONFIG]

# ---------------------------------------------------------------------------
# Symptom vocabulary: metric deviations an on-call engineer can observe.
# key -> (human label, telemetry metric it maps to, direction)
# ---------------------------------------------------------------------------
SYMPTOMS = {
    "throughput_drop": ("Throughput drop vs baseline", "throughput_eps", "low"),
    "consumer_lag_spike": ("Consumer lag spike", "consumer_lag", "high"),
    "producer_error_spike": ("Producer send error spike", "producer_error_rate", "high"),
    "broker_cpu_high": ("Broker CPU sustained high", "cluster_cpu_pct", "high"),
    "broker_memory_high": ("Broker memory pressure", "cluster_memory_pct", "high"),
    "disk_usage_high": ("Disk usage near capacity", "disk_usage_pct", "high"),
    "node_unresponsive": ("Cluster node unresponsive", "node_health", "low"),
    "indexing_latency_high": ("Indexing latency p95 high", "indexing_latency_p95_ms", "high"),
    "indexing_queue_backlog": ("Indexing queue backlog growing", "indexing_queue_depth", "high"),
    "segment_merge_pressure": ("Segment merge pressure high", "merge_ops_per_min", "high"),
    "ingestion_error_spike": ("Ingestion error rate spike", "ingestion_error_rate", "high"),
    "malformed_record_spike": ("Malformed record spike", "malformed_rate", "high"),
    "source_connection_failures": ("Source connection failures", "source_conn_failures", "high"),
    "recent_config_change": ("Recent configuration change", None, None),
    "auth_failure_spike": ("Authentication failure spike", "auth_failure_rate", "high"),
    "schema_mismatch_errors": ("Schema mismatch errors", "schema_error_rate", "high"),
}

# ---------------------------------------------------------------------------
# Signature: probability that each CORE symptom is present in an incident of
# the category. The generator samples core symptoms from these probabilities,
# then adds a small amount of cross-category noise. The diagnosis engine never
# sees this table; it uses its own scoring weights in diagnosis_engine.py.
# ---------------------------------------------------------------------------
SIGNATURES = {
    CAT_STREAMING: {
        "throughput_drop": 0.92,
        "consumer_lag_spike": 0.85,
        "producer_error_spike": 0.62,
    },
    CAT_CLUSTER: {
        "broker_cpu_high": 0.78,
        "broker_memory_high": 0.66,
        "disk_usage_high": 0.58,
        "node_unresponsive": 0.52,
    },
    CAT_INDEXING: {
        "indexing_latency_high": 0.93,
        "indexing_queue_backlog": 0.84,
        "segment_merge_pressure": 0.64,
    },
    CAT_INGESTION: {
        "ingestion_error_spike": 0.94,
        "malformed_record_spike": 0.58,
        "source_connection_failures": 0.66,
    },
    CAT_CONFIG: {
        "recent_config_change": 0.88,
        "auth_failure_spike": 0.55,
        "schema_mismatch_errors": 0.60,
    },
}

# Probability that any given non-core symptom appears as noise.
NOISE_PROB = 0.045

# ---------------------------------------------------------------------------
# Root causes per category. The generator picks one per incident; the engine
# ranks likely causes from the observed symptoms using CAUSE_HINTS.
# ---------------------------------------------------------------------------
ROOT_CAUSES = {
    CAT_STREAMING: [
        "Broker leader election loop after a rolling restart",
        "Consumer group rebalance storm caused by short session timeouts",
        "Network saturation on the replication path between brokers",
        "Undersized partition count for the peak traffic profile",
    ],
    CAT_CLUSTER: [
        "Disk filled by retained log segments beyond the retention policy",
        "JVM garbage collection pauses from an undersized heap",
        "Failed node with replicas not reassigned for several hours",
        "Sustained CPU saturation from unthrottled compaction jobs",
    ],
    CAT_INDEXING: [
        "Refresh interval too aggressive for the write volume",
        "Oversized bulk requests creating large unmerged segments",
        "Field explosion from unbounded dynamic mappings",
        "Merge throttling misconfigured after a version upgrade",
    ],
    CAT_INGESTION: [
        "Upstream source schema changed without notice",
        "Source database connection pool exhausted",
        "Corrupted batch files delivered by an upstream partner feed",
        "Connector task failed and did not restart automatically",
    ],
    CAT_CONFIG: [
        "Retention setting applied in the wrong unit (hours vs days)",
        "ACL change revoked the connector service account permissions",
        "Schema registry compatibility level raised without a migration",
        "Resource limit typo reduced the indexing thread pool to one",
    ],
}

# Which symptoms point at which root cause (used by the engine to rank causes).
CAUSE_HINTS = {
    CAT_STREAMING: {
        "node_unresponsive": "Broker leader election loop after a rolling restart",
        "consumer_lag_spike": "Consumer group rebalance storm caused by short session timeouts",
        "throughput_drop": "Network saturation on the replication path between brokers",
        "producer_error_spike": "Undersized partition count for the peak traffic profile",
    },
    CAT_CLUSTER: {
        "disk_usage_high": "Disk filled by retained log segments beyond the retention policy",
        "broker_memory_high": "JVM garbage collection pauses from an undersized heap",
        "node_unresponsive": "Failed node with replicas not reassigned for several hours",
        "broker_cpu_high": "Sustained CPU saturation from unthrottled compaction jobs",
    },
    CAT_INDEXING: {
        "indexing_queue_backlog": "Refresh interval too aggressive for the write volume",
        "segment_merge_pressure": "Oversized bulk requests creating large unmerged segments",
        "schema_mismatch_errors": "Field explosion from unbounded dynamic mappings",
        "indexing_latency_high": "Merge throttling misconfigured after a version upgrade",
    },
    CAT_INGESTION: {
        "schema_mismatch_errors": "Upstream source schema changed without notice",
        "source_connection_failures": "Source database connection pool exhausted",
        "malformed_record_spike": "Corrupted batch files delivered by an upstream partner feed",
        "ingestion_error_spike": "Connector task failed and did not restart automatically",
    },
    CAT_CONFIG: {
        "disk_usage_high": "Retention setting applied in the wrong unit (hours vs days)",
        "auth_failure_spike": "ACL change revoked the connector service account permissions",
        "schema_mismatch_errors": "Schema registry compatibility level raised without a migration",
        "indexing_latency_high": "Resource limit typo reduced the indexing thread pool to one",
    },
}

# ---------------------------------------------------------------------------
# Standard resolution steps per category (engine recommendations + runbooks).
# ---------------------------------------------------------------------------
RESOLUTION_STEPS = {
    CAT_STREAMING: [
        "Confirm scope: check throughput and consumer lag per topic and partition to isolate the affected pipeline.",
        "Inspect broker leader distribution and recent restart or deployment events on the affected brokers.",
        "Stabilize consumption: pause non-critical consumers, then restart the affected consumer group with an increased session timeout.",
        "Rebalance partition leadership and verify replication lag returns to zero on all replicas.",
        "Replay or reprocess any messages that exceeded retention during the outage window and confirm end-to-end counts with the source.",
        "Monitor lag and throughput for 30 minutes against baseline before closing the incident.",
    ],
    CAT_CLUSTER: [
        "Identify the unhealthy node from the cluster health endpoint and cordon it from client traffic.",
        "Check disk, heap, and garbage collection logs on the affected node to confirm the resource bottleneck.",
        "Free space or expand the volume if disk pressure is the driver; restart the node process if memory pressure persists after a heap dump is captured.",
        "Reassign replicas from the failed or degraded node and watch under-replicated partition counts return to zero.",
        "Raise the heap or throttle background compaction if GC or CPU saturation is the confirmed driver, then schedule the permanent fix.",
        "Verify all nodes report green status and client error rates are back to baseline before closing.",
    ],
    CAT_INDEXING: [
        "Confirm the bottleneck is indexing, not query load: compare indexing latency p95 and queue depth against search latency.",
        "Inspect segment counts and merge activity; force a merge only during a low-traffic window if segment counts are extreme.",
        "Reduce bulk request sizes and split oversized batches so segments stay within the target size range.",
        "Raise the refresh interval to the agreed value for high-volume indices and re-check latency after one full cycle.",
        "Review dynamic mapping settings and add explicit mappings for new fields to stop field explosion.",
        "Track indexing latency p95 and queue depth for one hour to confirm the improvement holds under normal load.",
    ],
    CAT_INGESTION: [
        "Identify the failing connector or source from the ingestion error stream and pause it to stop error amplification.",
        "Compare a sample of rejected records against the registered schema to find the exact mismatch or corruption pattern.",
        "Restore source connectivity: reset the exhausted connection pool or restart the failed connector task.",
        "Quarantine malformed records to the dead letter queue with the rejection reason attached for later replay.",
        "Apply the schema mapping fix or partner feed correction, then resume ingestion at a reduced rate.",
        "Backfill the gap window from the source and reconcile record counts before closing the incident.",
    ],
    CAT_CONFIG: [
        "Diff the current configuration against the last known good version in the change log to isolate the offending change.",
        "Roll back the single offending setting first rather than the whole change set, and note the rollback in the incident record.",
        "Restore the service account permissions or compatibility level that the change altered, using the principle of least privilege.",
        "Restart only the affected component so the corrected setting takes effect with minimal blast radius.",
        "Validate with a smoke test: produce, consume, and index a synthetic record end to end.",
        "Add the setting to the pre-deployment checklist and require a second reviewer for that configuration class.",
    ],
}

PIPELINES = [
    ("PIPE-ORDERS", "CL-EAST-1"),
    ("PIPE-PAYMENTS", "CL-EAST-1"),
    ("PIPE-CLICKSTREAM", "CL-WEST-2"),
    ("PIPE-IOT-TELEMETRY", "CL-WEST-2"),
    ("PIPE-INVENTORY", "CL-CENTRAL-1"),
    ("PIPE-CRM-SYNC", "CL-CENTRAL-1"),
]

SEVERITIES = ["SEV1", "SEV2", "SEV3", "SEV4"]
