"""Generate the synthetic StreamGuard telemetry time series.

Hourly metrics for six pipelines across three clusters over 90 days.
Baselines follow a diurnal pattern with noise. During each incident window
(from data/generate_incidents.py), the metrics named by the incident's
symptom signature are pushed to deviating values, which is what the anomaly
detection in detection/anomaly_detection.py later has to find again.

Run directly to write data/telemetry.csv:
    python3 data/generate_telemetry.py
"""

import csv
import math
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from generate_incidents import START, WINDOW_DAYS, generate_incidents  # noqa: E402
from sg_common import PIPELINES  # noqa: E402

SEED = 42

# Baseline throughput (events per second) per pipeline.
BASE_THROUGHPUT = {
    "PIPE-ORDERS": 4200,
    "PIPE-PAYMENTS": 2600,
    "PIPE-CLICKSTREAM": 18500,
    "PIPE-IOT-TELEMETRY": 9800,
    "PIPE-INVENTORY": 1400,
    "PIPE-CRM-SYNC": 850,
}

FIELDS = [
    "timestamp",
    "pipeline",
    "cluster",
    "throughput_eps",
    "consumer_lag",
    "producer_error_rate",
    "cluster_cpu_pct",
    "cluster_memory_pct",
    "disk_usage_pct",
    "node_health",
    "indexing_latency_p95_ms",
    "indexing_queue_depth",
    "merge_ops_per_min",
    "ingestion_error_rate",
    "malformed_rate",
    "source_conn_failures",
    "auth_failure_rate",
    "schema_error_rate",
]


def _baseline_row(rng, ts, pipeline):
    hour = ts.hour
    diurnal = 1.0 + 0.28 * math.sin((hour - 8) / 24.0 * 2 * math.pi)
    base = BASE_THROUGHPUT[pipeline]
    throughput = base * diurnal * rng.uniform(0.92, 1.08)
    return {
        "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
        "pipeline": pipeline,
        "cluster": dict(PIPELINES)[pipeline],
        "throughput_eps": round(throughput, 1),
        "consumer_lag": int(throughput * rng.uniform(0.05, 0.22)),
        "producer_error_rate": round(rng.uniform(0.0002, 0.0015), 5),
        "cluster_cpu_pct": round(rng.uniform(34, 58), 1),
        "cluster_memory_pct": round(rng.uniform(48, 68), 1),
        "disk_usage_pct": round(rng.uniform(52, 71), 1),
        "node_health": 1.0,
        "indexing_latency_p95_ms": int(rng.uniform(38, 85)),
        "indexing_queue_depth": int(rng.uniform(20, 240)),
        "merge_ops_per_min": round(rng.uniform(4, 11), 1),
        "ingestion_error_rate": round(rng.uniform(0.0005, 0.003), 5),
        "malformed_rate": round(rng.uniform(0.0002, 0.0012), 5),
        "source_conn_failures": rng.choice([0, 0, 0, 1]),
        "auth_failure_rate": round(rng.uniform(0.0001, 0.0008), 5),
        "schema_error_rate": round(rng.uniform(0.0001, 0.0009), 5),
    }


def _apply_symptoms(row, symptoms, rng):
    """Push the metrics for each present symptom to deviating values."""
    if "throughput_drop" in symptoms:
        row["throughput_eps"] = round(row["throughput_eps"] * rng.uniform(0.3, 0.55), 1)
    if "consumer_lag_spike" in symptoms:
        row["consumer_lag"] = int(row["consumer_lag"] * rng.uniform(7, 14) + 6000)
    if "producer_error_spike" in symptoms:
        row["producer_error_rate"] = round(rng.uniform(0.05, 0.12), 5)
    if "broker_cpu_high" in symptoms:
        row["cluster_cpu_pct"] = round(rng.uniform(88, 97), 1)
    if "broker_memory_high" in symptoms:
        row["cluster_memory_pct"] = round(rng.uniform(90, 98), 1)
    if "disk_usage_high" in symptoms:
        row["disk_usage_pct"] = round(rng.uniform(93, 99), 1)
    if "node_unresponsive" in symptoms:
        row["node_health"] = 0.67
    if "indexing_latency_high" in symptoms:
        row["indexing_latency_p95_ms"] = int(row["indexing_latency_p95_ms"] * rng.uniform(5, 9))
    if "indexing_queue_backlog" in symptoms:
        row["indexing_queue_depth"] = int(row["indexing_queue_depth"] * rng.uniform(8, 15) + 1500)
    if "segment_merge_pressure" in symptoms:
        row["merge_ops_per_min"] = round(row["merge_ops_per_min"] * rng.uniform(2.6, 4.2), 1)
    if "ingestion_error_spike" in symptoms:
        row["ingestion_error_rate"] = round(rng.uniform(0.08, 0.2), 5)
    if "malformed_record_spike" in symptoms:
        row["malformed_rate"] = round(rng.uniform(0.05, 0.15), 5)
    if "source_connection_failures" in symptoms:
        row["source_conn_failures"] = rng.randrange(20, 60)
    if "auth_failure_spike" in symptoms:
        row["auth_failure_rate"] = round(rng.uniform(0.04, 0.1), 5)
    if "schema_mismatch_errors" in symptoms:
        row["schema_error_rate"] = round(rng.uniform(0.05, 0.12), 5)
    return row


def generate_telemetry(seed=SEED, incidents=None):
    if incidents is None:
        incidents = generate_incidents()
    # Index incident windows per pipeline: list of (start_hour, end_hour, symptoms)
    windows = {p: [] for p, _ in PIPELINES}
    for inc in incidents:
        start = datetime.strptime(inc["start_time"], "%Y-%m-%d %H:%M")
        end = datetime.strptime(inc["end_time"], "%Y-%m-%d %H:%M")
        symptoms = inc["symptoms"].split(";") if inc["symptoms"] else []
        windows[inc["pipeline"]].append((start, end, symptoms, inc["incident_id"]))

    rows = []
    total_hours = WINDOW_DAYS * 24
    for p_idx, (pipeline, _cluster) in enumerate(PIPELINES):
        rng = random.Random(seed + p_idx * 7919)
        for h in range(total_hours):
            ts = START + timedelta(hours=h)
            row = _baseline_row(rng, ts, pipeline)
            for (w_start, w_end, symptoms, inc_id) in windows[pipeline]:
                if w_start <= ts <= w_end:
                    irng = random.Random(seed + int(inc_id.split("-")[1]) * 131 + h)
                    row = _apply_symptoms(row, symptoms, irng)
            rows.append(row)
    rows.sort(key=lambda r: (r["timestamp"], r["pipeline"]))
    return rows


def main():
    out = os.path.join(os.path.dirname(__file__), "telemetry.csv")
    rows = generate_telemetry()
    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} telemetry rows to {out}")


if __name__ == "__main__":
    main()
