"""Anomaly detection over the StreamGuard telemetry.

Method: for each pipeline and each monitored metric, compute a rolling
baseline (previous 48 hours: mean and standard deviation). A point is
anomalous when it breaches an absolute threshold from the diagnosis engine's
snapshot table OR its z-score against the rolling baseline exceeds 3.5 in
the deviating direction. Consecutive anomalous hours are grouped into
detection windows per pipeline.

Coverage: an incident counts as detected when at least one detection window
on the same pipeline overlaps the incident window or starts within 2 hours
after the incident start. Writes output/detection_results.json.

    python3 detection/anomaly_detection.py
"""

import csv
import json
import os
import statistics
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
from diagnosis_engine import SNAPSHOT_THRESHOLDS  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROLLING_HOURS = 48
Z_LIMIT = 3.5
MATCH_SLACK = timedelta(hours=2)

# metric -> direction of deviation ("high" or "low")
MONITORED = {}
for metric, (_symptom, _thr, op) in SNAPSHOT_THRESHOLDS.items():
    MONITORED[metric] = "low" if op == "lt" else "high"
MONITORED["throughput_eps"] = "low"


def _is_anomalous(metric, value, history):
    symptom, threshold, op = SNAPSHOT_THRESHOLDS.get(metric, (None, None, None))
    if op == "gt" and value > threshold:
        return True
    if op == "lt" and value < threshold:
        return True
    if op == "gte" and value >= threshold:
        return True
    if metric == "throughput_eps" and len(history) >= 24:
        mean = statistics.fmean(history)
        if value < 0.62 * mean:
            return True
    if len(history) >= 24:
        mean = statistics.fmean(history)
        stdev = statistics.pstdev(history)
        if stdev > 0:
            z = (value - mean) / stdev
            if MONITORED[metric] == "high" and z > Z_LIMIT:
                return True
            if MONITORED[metric] == "low" and z < -Z_LIMIT:
                return True
    return False


def detect(telemetry_path=None, incidents_path=None):
    tpath = telemetry_path or os.path.join(ROOT, "data", "telemetry.csv")
    ipath = incidents_path or os.path.join(ROOT, "data", "incidents.csv")

    series = {}  # pipeline -> list of (datetime, row)
    with open(tpath) as fh:
        for row in csv.DictReader(fh):
            ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M")
            series.setdefault(row["pipeline"], []).append((ts, row))
    for pipeline in series:
        series[pipeline].sort(key=lambda x: x[0])

    windows = []  # (pipeline, start, end)
    total_points = 0
    anomalous_points = 0
    for pipeline, points in series.items():
        history = {m: [] for m in MONITORED}
        open_start = None
        last_anomalous = None
        for ts, row in points:
            total_points += 1
            anomalous = False
            for metric in MONITORED:
                value = float(row[metric])
                if _is_anomalous(metric, value, history[metric]):
                    anomalous = True
                history[metric].append(value)
                if len(history[metric]) > ROLLING_HOURS:
                    history[metric].pop(0)
            if anomalous:
                anomalous_points += 1
                if open_start is None:
                    open_start = ts
                last_anomalous = ts
            else:
                if open_start is not None and last_anomalous is not None and ts - last_anomalous > timedelta(hours=2):
                    windows.append((pipeline, open_start, last_anomalous))
                    open_start = None
                    last_anomalous = None
        if open_start is not None:
            windows.append((pipeline, open_start, last_anomalous))

    incidents = []
    with open(ipath) as fh:
        for row in csv.DictReader(fh):
            incidents.append(
                (
                    row["incident_id"],
                    row["pipeline"],
                    datetime.strptime(row["start_time"], "%Y-%m-%d %H:%M"),
                    datetime.strptime(row["end_time"], "%Y-%m-%d %H:%M"),
                    row["category"],
                )
            )
    detected = 0
    missed = []
    per_category = {}
    for inc_id, pipeline, start, end, category in incidents:
        hit = any(
            wp == pipeline and ws <= end + MATCH_SLACK and we >= start - MATCH_SLACK
            for (wp, ws, we) in windows
        )
        stats = per_category.setdefault(category, {"total": 0, "detected": 0})
        stats["total"] += 1
        if hit:
            detected += 1
            stats["detected"] += 1
        else:
            missed.append(inc_id)
    for stats in per_category.values():
        stats["coverage"] = round(stats["detected"] / stats["total"], 4) if stats["total"] else 0.0

    results = {
        "telemetry_points_checked": total_points,
        "anomalous_points": anomalous_points,
        "detection_windows": len(windows),
        "incidents_total": len(incidents),
        "incidents_detected": detected,
        "detection_coverage": round(detected / len(incidents), 4) if incidents else 0.0,
        "per_category_coverage": per_category,
        "missed_incident_ids": missed[:25],
        "method": (
            "Rolling 48h mean/std z-score (limit 3.5) plus absolute thresholds "
            "from the diagnosis engine snapshot table; windows grouped per "
            "pipeline; incident matched when a window overlaps the incident "
            "window or starts within 2 hours of incident start."
        ),
    }
    return results


def main():
    results = detect()
    out = os.path.join(ROOT, "output", "detection_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"Telemetry points checked: {results['telemetry_points_checked']}")
    print(f"Detection windows: {results['detection_windows']}")
    print(f"Detection coverage: {results['detection_coverage']:.4f} "
          f"({results['incidents_detected']}/{results['incidents_total']})")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
