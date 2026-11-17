"""StreamGuard rule-based diagnosis engine.

Input: a set of observed symptoms (metric deviations), either given directly
or derived from a telemetry snapshot. Output: the predicted incident
category, a confidence level, the most likely root causes, and the
recommended resolution steps from the runbook for that category.

The engine is deliberately rule-based and explainable: every symptom carries
points toward one or more categories (WEIGHTS below), the category with the
highest total wins, and confidence reflects how clearly it wins. The engine
never sees the ground-truth label of an incident; evaluation lives in
engine/evaluate_engine.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sg_common import (  # noqa: E402
    CATEGORIES,
    CAUSE_HINTS,
    RESOLUTION_STEPS,
    ROOT_CAUSES,
    CAT_CLUSTER,
    CAT_CONFIG,
    CAT_INDEXING,
    CAT_INGESTION,
    CAT_STREAMING,
)

# Points each symptom awards to each category. Primary signal = 3,
# plausible secondary association = 1 or 2.
WEIGHTS = {
    "throughput_drop": {CAT_STREAMING: 3, CAT_INGESTION: 1},
    "consumer_lag_spike": {CAT_STREAMING: 3, CAT_CLUSTER: 1},
    "producer_error_spike": {CAT_STREAMING: 3, CAT_CONFIG: 1},
    "broker_cpu_high": {CAT_CLUSTER: 3, CAT_INDEXING: 1},
    "broker_memory_high": {CAT_CLUSTER: 3},
    "disk_usage_high": {CAT_CLUSTER: 3, CAT_CONFIG: 1},
    "node_unresponsive": {CAT_CLUSTER: 3, CAT_STREAMING: 1},
    "indexing_latency_high": {CAT_INDEXING: 3, CAT_CLUSTER: 1, CAT_CONFIG: 1},
    "indexing_queue_backlog": {CAT_INDEXING: 3},
    "segment_merge_pressure": {CAT_INDEXING: 3},
    "ingestion_error_spike": {CAT_INGESTION: 3, CAT_CONFIG: 1},
    "malformed_record_spike": {CAT_INGESTION: 3},
    "source_connection_failures": {CAT_INGESTION: 3, CAT_CLUSTER: 1},
    "recent_config_change": {CAT_CONFIG: 3, CAT_INDEXING: 1},
    "auth_failure_spike": {CAT_CONFIG: 3, CAT_INGESTION: 1},
    "schema_mismatch_errors": {CAT_CONFIG: 2, CAT_INGESTION: 2, CAT_INDEXING: 1},
}

# Absolute thresholds used to turn a telemetry snapshot into symptoms.
SNAPSHOT_THRESHOLDS = {
    "cluster_cpu_pct": ("broker_cpu_high", 85, "gt"),
    "cluster_memory_pct": ("broker_memory_high", 85, "gt"),
    "disk_usage_pct": ("disk_usage_high", 90, "gt"),
    "node_health": ("node_unresponsive", 1.0, "lt"),
    "indexing_latency_p95_ms": ("indexing_latency_high", 250, "gt"),
    "indexing_queue_depth": ("indexing_queue_backlog", 1000, "gt"),
    "merge_ops_per_min": ("segment_merge_pressure", 25, "gt"),
    "ingestion_error_rate": ("ingestion_error_spike", 0.02, "gt"),
    "malformed_rate": ("malformed_record_spike", 0.02, "gt"),
    "source_conn_failures": ("source_connection_failures", 10, "gte"),
    "auth_failure_rate": ("auth_failure_spike", 0.01, "gt"),
    "schema_error_rate": ("schema_mismatch_errors", 0.01, "gt"),
    "producer_error_rate": ("producer_error_spike", 0.01, "gt"),
    "consumer_lag": ("consumer_lag_spike", 15000, "gt"),
}


def symptoms_from_snapshot(snapshot, baseline_throughput=None):
    """Convert a telemetry metric snapshot (dict of metric -> value) to symptoms."""
    symptoms = []
    for metric, (symptom, threshold, op) in SNAPSHOT_THRESHOLDS.items():
        if metric not in snapshot:
            continue
        value = snapshot[metric]
        if (op == "gt" and value > threshold) or (op == "lt" and value < threshold) or (
            op == "gte" and value >= threshold
        ):
            symptoms.append(symptom)
    if baseline_throughput and snapshot.get("throughput_eps") is not None:
        if snapshot["throughput_eps"] < 0.7 * baseline_throughput:
            symptoms.append("throughput_drop")
    if snapshot.get("recent_config_change"):
        symptoms.append("recent_config_change")
    return symptoms


def score_categories(symptoms):
    scores = {c: 0 for c in CATEGORIES}
    for symptom in symptoms:
        for category, points in WEIGHTS.get(symptom, {}).items():
            scores[category] += points
    return scores


def _rank_root_causes(category, symptoms):
    hints = CAUSE_HINTS.get(category, {})
    hinted = [hints[s] for s in symptoms if s in hints]
    ranked = []
    for cause in hinted + ROOT_CAUSES[category]:
        if cause not in ranked:
            ranked.append(cause)
    return ranked


def diagnose(symptoms):
    """Diagnose from a list of symptom keys. Returns a result dict."""
    symptoms = list(dict.fromkeys(symptoms))  # dedupe, keep order
    scores = score_categories(symptoms)
    total = sum(scores.values())
    if total == 0:
        return {
            "predicted_category": None,
            "confidence": 0.0,
            "scores": scores,
            "likely_root_causes": [],
            "recommended_steps": [],
            "symptoms_used": symptoms,
        }
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_category, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    # Confidence: share of total points, lifted by the margin over second place.
    share = top_score / total
    margin = (top_score - second_score) / top_score if top_score else 0
    confidence = round(min(0.99, 0.5 * share + 0.5 * margin + 0.25 * share), 2)
    confidence = max(confidence, round(share, 2))
    return {
        "predicted_category": top_category,
        "confidence": confidence,
        "scores": scores,
        "likely_root_causes": _rank_root_causes(top_category, symptoms)[:2],
        "recommended_steps": RESOLUTION_STEPS[top_category],
        "symptoms_used": symptoms,
    }


def diagnose_snapshot(snapshot, baseline_throughput=None):
    return diagnose(symptoms_from_snapshot(snapshot, baseline_throughput))


if __name__ == "__main__":
    demo = ["consumer_lag_spike", "throughput_drop", "producer_error_spike"]
    result = diagnose(demo)
    print("Symptoms:", ", ".join(demo))
    print("Predicted:", result["predicted_category"], "| confidence:", result["confidence"])
    print("Likely root cause:", result["likely_root_causes"][0])
