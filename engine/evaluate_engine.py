"""Evaluate the diagnosis engine against the labeled incident dataset.

Runs engine.diagnose() on the symptom signature of every incident in
data/incidents.csv and compares the prediction with the ground-truth label.
Writes output/evaluation_results.json and prints a summary including overall
accuracy, per-category accuracy, and the confusion counts.

    python3 engine/evaluate_engine.py
"""

import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from diagnosis_engine import diagnose  # noqa: E402
from sg_common import CATEGORIES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def evaluate(incidents_path=None):
    path = incidents_path or os.path.join(ROOT, "data", "incidents.csv")
    confusion = {actual: {pred: 0 for pred in CATEGORIES} for actual in CATEGORIES}
    totals = defaultdict(int)
    correct = defaultdict(int)
    confidences = []
    n = 0
    with open(path) as fh:
        for row in csv.DictReader(fh):
            symptoms = row["symptoms"].split(";") if row["symptoms"] else []
            result = diagnose(symptoms)
            pred = result["predicted_category"]
            actual = row["category"]
            totals[actual] += 1
            n += 1
            if pred in confusion[actual]:
                confusion[actual][pred] += 1
            if pred == actual:
                correct[actual] += 1
            confidences.append(result["confidence"])
    per_category = {
        c: {
            "total": totals[c],
            "correct": correct[c],
            "accuracy": round(correct[c] / totals[c], 4) if totals[c] else 0.0,
        }
        for c in CATEGORIES
    }
    overall_correct = sum(correct.values())
    results = {
        "incidents_evaluated": n,
        "overall_correct": overall_correct,
        "overall_accuracy": round(overall_correct / n, 4) if n else 0.0,
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "per_category": per_category,
        "confusion": confusion,
    }
    return results


def main():
    results = evaluate()
    out = os.path.join(ROOT, "output", "evaluation_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"Incidents evaluated: {results['incidents_evaluated']}")
    print(f"Overall accuracy: {results['overall_accuracy']:.4f} "
          f"({results['overall_correct']}/{results['incidents_evaluated']})")
    for cat, stats in results["per_category"].items():
        print(f"  {cat}: {stats['accuracy']:.4f} ({stats['correct']}/{stats['total']})")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
