"""StreamGuard test suite (Python standard library unittest only).

Covers: generator reproducibility, diagnosis engine classification on known
symptom cases for all five categories, snapshot conversion, and KPI math on
known inputs.

    python3 -m unittest discover -s tests
"""

import os
import sys
import unittest
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data"))
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "analysis"))

from generate_incidents import generate_incidents  # noqa: E402
from generate_telemetry import generate_telemetry  # noqa: E402
from diagnosis_engine import diagnose, symptoms_from_snapshot  # noqa: E402
from run_analysis import analyze  # noqa: E402
from sg_common import (  # noqa: E402
    CAT_CLUSTER,
    CAT_CONFIG,
    CAT_INDEXING,
    CAT_INGESTION,
    CAT_STREAMING,
)


class TestIncidentGenerator(unittest.TestCase):
    def test_reproducible_same_seed(self):
        a = generate_incidents(seed=42, n=60)
        b = generate_incidents(seed=42, n=60)
        self.assertEqual(a, b)

    def test_count_and_aggregates(self):
        rows = generate_incidents(seed=42, n=60)
        self.assertEqual(len(rows), 60)
        self.assertEqual(
            sum(r["resolution_minutes"] for r in rows),
            sum(r["resolution_minutes"] for r in generate_incidents(seed=42, n=60)),
        )
        self.assertTrue(all(r["status"] == "Resolved" for r in rows))
        self.assertTrue(all(1 <= r["csat"] <= 5 for r in rows))

    def test_different_seed_differs(self):
        a = generate_incidents(seed=42, n=60)
        b = generate_incidents(seed=7, n=60)
        self.assertNotEqual(
            [r["symptoms"] for r in a], [r["symptoms"] for r in b]
        )

    def test_all_categories_present_in_full_run(self):
        rows = generate_incidents(seed=42, n=384)
        cats = {r["category"] for r in rows}
        self.assertEqual(len(cats), 5)
        self.assertEqual(len(rows), 384)


class TestTelemetryGenerator(unittest.TestCase):
    def test_reproducible(self):
        incidents = generate_incidents(seed=42, n=12)
        a = generate_telemetry(seed=42, incidents=incidents)
        b = generate_telemetry(seed=42, incidents=incidents)
        self.assertEqual(len(a), 90 * 24 * 6)
        self.assertEqual(a[:500], b[:500])
        self.assertEqual(a, b)


class TestDiagnosisEngine(unittest.TestCase):
    def test_streaming_case(self):
        result = diagnose(["throughput_drop", "consumer_lag_spike", "producer_error_spike"])
        self.assertEqual(result["predicted_category"], CAT_STREAMING)
        self.assertGreater(result["confidence"], 0.5)
        self.assertTrue(result["recommended_steps"])

    def test_cluster_case(self):
        result = diagnose(
            ["broker_cpu_high", "broker_memory_high", "disk_usage_high", "node_unresponsive"]
        )
        self.assertEqual(result["predicted_category"], CAT_CLUSTER)

    def test_indexing_case(self):
        result = diagnose(
            ["indexing_latency_high", "indexing_queue_backlog", "segment_merge_pressure"]
        )
        self.assertEqual(result["predicted_category"], CAT_INDEXING)

    def test_ingestion_case(self):
        result = diagnose(
            ["ingestion_error_spike", "malformed_record_spike", "source_connection_failures"]
        )
        self.assertEqual(result["predicted_category"], CAT_INGESTION)

    def test_config_case(self):
        result = diagnose(["recent_config_change", "auth_failure_spike"])
        self.assertEqual(result["predicted_category"], CAT_CONFIG)

    def test_empty_symptoms(self):
        result = diagnose([])
        self.assertIsNone(result["predicted_category"])
        self.assertEqual(result["confidence"], 0.0)

    def test_snapshot_conversion(self):
        snapshot = {
            "cluster_cpu_pct": 93.0,
            "cluster_memory_pct": 91.0,
            "disk_usage_pct": 40.0,
            "node_health": 1.0,
            "consumer_lag": 120,
        }
        symptoms = symptoms_from_snapshot(snapshot)
        self.assertIn("broker_cpu_high", symptoms)
        self.assertIn("broker_memory_high", symptoms)
        self.assertNotIn("disk_usage_high", symptoms)
        self.assertNotIn("consumer_lag_spike", symptoms)


def _fake_row(category, severity, minutes, csat, escalated, cause, day):
    return {
        "category": category,
        "severity": severity,
        "resolution_minutes": minutes,
        "csat": csat,
        "escalated": escalated,
        "root_cause": cause,
        "pipeline": "PIPE-ORDERS",
        "start_time": f"2026-01-{day:02d} 10:00",
        "start_dt": datetime(2026, 1, day, 10, 0),
    }


class TestKpiMath(unittest.TestCase):
    def test_known_inputs(self):
        rows = [
            _fake_row(CAT_STREAMING, "SEV2", 100, 5, "no", "Cause A", 1),
            _fake_row(CAT_STREAMING, "SEV3", 200, 4, "yes", "Cause A", 2),
            _fake_row(CAT_CONFIG, "SEV4", 60, 5, "no", "Cause B", 3),
            _fake_row(CAT_CONFIG, "SEV4", 40, 5, "no", "Cause B", 4),
        ]
        results = analyze(rows)
        self.assertEqual(results["total_incidents"], 4)
        self.assertEqual(results["overall_mttr_minutes"], 100.0)  # (100+200+60+40)/4
        self.assertEqual(results["csat"]["mean"], 4.75)  # (5+4+5+5)/4
        self.assertEqual(results["by_category"][CAT_STREAMING]["mttr_minutes"], 150.0)
        self.assertEqual(results["by_category"][CAT_CONFIG]["count"], 2)
        self.assertEqual(results["escalation"]["escalated_count"], 1)
        self.assertEqual(results["escalation"]["escalation_rate"], 0.25)


if __name__ == "__main__":
    unittest.main()
