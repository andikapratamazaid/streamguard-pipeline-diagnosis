"""Generate the synthetic StreamGuard incident dataset.

Produces roughly 380 incidents over a 90 day window, each labeled with one of
the five categories defined in sg_common.py. Symptom signatures are sampled
from the per-category signature probabilities, with a small amount of
cross-category noise, so the diagnosis engine has a realistic (not perfect)
signal to work from.

Run directly to write data/incidents.csv:
    python3 data/generate_incidents.py
"""

import csv
import math
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sg_common import (  # noqa: E402
    CATEGORIES,
    NOISE_PROB,
    PIPELINES,
    RESOLUTION_STEPS,
    ROOT_CAUSES,
    SIGNATURES,
    SYMPTOMS,
    CAT_CLUSTER,
    CAT_CONFIG,
    CAT_INDEXING,
    CAT_INGESTION,
    CAT_STREAMING,
)

SEED = 42
N_INCIDENTS = 384
START = datetime(2026, 1, 1, 0, 0, 0)
WINDOW_DAYS = 90

CATEGORY_WEIGHTS = {
    CAT_STREAMING: 0.26,
    CAT_CLUSTER: 0.20,
    CAT_INDEXING: 0.22,
    CAT_INGESTION: 0.20,
    CAT_CONFIG: 0.12,
}

SEVERITY_WEIGHTS = {
    CAT_STREAMING: [0.08, 0.32, 0.40, 0.20],
    CAT_CLUSTER: [0.10, 0.34, 0.38, 0.18],
    CAT_INDEXING: [0.04, 0.28, 0.44, 0.24],
    CAT_INGESTION: [0.06, 0.30, 0.42, 0.22],
    CAT_CONFIG: [0.03, 0.22, 0.45, 0.30],
}
SEVERITY_LABELS = ["SEV1", "SEV2", "SEV3", "SEV4"]
SEVERITY_TIME_FACTOR = {"SEV1": 1.8, "SEV2": 1.25, "SEV3": 1.0, "SEV4": 0.7}
ESCALATION_PROB = {"SEV1": 0.55, "SEV2": 0.30, "SEV3": 0.12, "SEV4": 0.04}

# Median resolution minutes per category before the severity factor.
BASE_RESOLUTION = {
    CAT_STREAMING: 95,
    CAT_CLUSTER: 210,
    CAT_INDEXING: 150,
    CAT_INGESTION: 120,
    CAT_CONFIG: 65,
}


def _weighted_choice(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _sample_symptoms(rng, category):
    core = SIGNATURES[category]
    present = [s for s, p in core.items() if rng.random() < p]
    # An incident always shows at least two of its core symptoms.
    if len(present) < 2:
        missing = [s for s in core if s not in present]
        rng.shuffle(missing)
        present.extend(missing[: 2 - len(present)])
    for symptom in SYMPTOMS:
        if symptom not in core and rng.random() < NOISE_PROB:
            present.append(symptom)
    rng.shuffle(present)
    return present


def _sample_csat(rng, resolution_minutes):
    # Heavily weighted to 5; long resolutions drag a few scores down.
    weights = [0.88, 0.08, 0.025, 0.010, 0.005]  # scores 5,4,3,2,1
    if resolution_minutes > 300:
        weights = [0.74, 0.16, 0.06, 0.025, 0.015]
    elif resolution_minutes > 180:
        weights = [0.82, 0.12, 0.04, 0.012, 0.008]
    return rng.choices([5, 4, 3, 2, 1], weights=weights, k=1)[0]


def generate_incidents(seed=SEED, n=N_INCIDENTS):
    rng = random.Random(seed)
    incidents = []
    total_minutes = WINDOW_DAYS * 24 * 60
    for i in range(n):
        category = _weighted_choice(
            rng, CATEGORIES, [CATEGORY_WEIGHTS[c] for c in CATEGORIES]
        )
        pipeline, cluster = rng.choice(PIPELINES)
        offset = rng.randrange(0, total_minutes)
        start = START + timedelta(minutes=offset)
        severity = _weighted_choice(rng, SEVERITY_LABELS, SEVERITY_WEIGHTS[category])
        median = BASE_RESOLUTION[category] * SEVERITY_TIME_FACTOR[severity]
        resolution = int(rng.lognormvariate(math.log(median), 0.45))
        resolution = max(8, min(resolution, 1440))
        end = start + timedelta(minutes=resolution)
        symptoms = _sample_symptoms(rng, category)
        root_cause = rng.choice(ROOT_CAUSES[category])
        escalated = "yes" if rng.random() < ESCALATION_PROB[severity] else "no"
        csat = _sample_csat(rng, resolution)
        incidents.append(
            {
                "incident_id": "",  # assigned after sorting
                "start_time": start.strftime("%Y-%m-%d %H:%M"),
                "end_time": end.strftime("%Y-%m-%d %H:%M"),
                "pipeline": pipeline,
                "cluster": cluster,
                "category": category,
                "severity": severity,
                "symptoms": ";".join(symptoms),
                "root_cause": root_cause,
                "resolution_steps_taken": " >> ".join(RESOLUTION_STEPS[category]),
                "resolution_minutes": resolution,
                "escalated": escalated,
                "csat": csat,
                "status": "Resolved",
            }
        )
    incidents.sort(key=lambda r: r["start_time"])
    for idx, row in enumerate(incidents, start=1):
        row["incident_id"] = f"INC-{idx:04d}"
    return incidents


FIELDS = [
    "incident_id",
    "start_time",
    "end_time",
    "pipeline",
    "cluster",
    "category",
    "severity",
    "symptoms",
    "root_cause",
    "resolution_steps_taken",
    "resolution_minutes",
    "escalated",
    "csat",
    "status",
]


def main():
    out = os.path.join(os.path.dirname(__file__), "incidents.csv")
    rows = generate_incidents()
    with open(out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} incidents to {out}")


if __name__ == "__main__":
    main()
