"""StreamGuard incident analytics.

Computes MTTR by category and severity, incident volume trend, recurring
problem analysis, CSAT analysis, and escalation patterns from
data/incidents.csv. Produces PNG charts in analysis/charts/, the machine
readable summary output/analysis_results.json, and analysis/findings.md
generated from the same computed numbers so the document can never drift
from the data.

    python3 analysis/run_analysis.py
"""

import csv
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sg_common import CATEGORIES, SEVERITIES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
CHART_DIR = os.path.join(os.path.dirname(__file__), "charts")

COLORS = {
    "Streaming Pipeline Failure": "#2563eb",
    "Cluster Health Degradation": "#dc2626",
    "Indexing Performance Bottleneck": "#d97706",
    "Data Ingestion Failure": "#059669",
    "Configuration Error": "#7c3aed",
}
SHORT = {
    "Streaming Pipeline Failure": "Streaming",
    "Cluster Health Degradation": "Cluster",
    "Indexing Performance Bottleneck": "Indexing",
    "Data Ingestion Failure": "Ingestion",
    "Configuration Error": "Config",
}


def _mean(values):
    return round(statistics.fmean(values), 2) if values else 0.0


def _median(values):
    return round(statistics.median(values), 2) if values else 0.0


def load_incidents():
    path = os.path.join(ROOT, "data", "incidents.csv")
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["resolution_minutes"] = int(row["resolution_minutes"])
        row["csat"] = int(row["csat"])
        row["start_dt"] = datetime.strptime(row["start_time"], "%Y-%m-%d %H:%M")
    return rows


def analyze(rows):
    total = len(rows)
    by_category = {}
    for cat in CATEGORIES:
        subset = [r for r in rows if r["category"] == cat]
        times = [r["resolution_minutes"] for r in subset]
        by_category[cat] = {
            "count": len(subset),
            "share_pct": round(100 * len(subset) / total, 2),
            "mttr_minutes": _mean(times),
            "median_minutes": _median(times),
            "p90_minutes": round(sorted(times)[int(0.9 * len(times)) - 1], 2) if times else 0,
            "csat_mean": _mean([r["csat"] for r in subset]),
            "escalation_rate": round(
                sum(1 for r in subset if r["escalated"] == "yes") / len(subset), 4
            ) if subset else 0.0,
        }
    by_severity = {}
    for sev in SEVERITIES:
        subset = [r for r in rows if r["severity"] == sev]
        by_severity[sev] = {
            "count": len(subset),
            "mttr_minutes": _mean([r["resolution_minutes"] for r in subset]),
            "escalation_rate": round(
                sum(1 for r in subset if r["escalated"] == "yes") / len(subset), 4
            ) if subset else 0.0,
        }
    # Weekly volume trend (ISO weeks from the dataset start).
    start = min(r["start_dt"] for r in rows)
    weekly = Counter()
    for r in rows:
        week = (r["start_dt"] - start).days // 7
        weekly[week] += 1
    weeks_sorted = sorted(weekly.items())
    # Recurring problems: root causes seen at least 15 times in 90 days.
    cause_counts = Counter(r["root_cause"] for r in rows)
    recurring = [
        {"root_cause": cause, "count": count}
        for cause, count in cause_counts.most_common()
        if count >= 15
    ]
    recurring_incidents = sum(item["count"] for item in recurring)
    # CSAT.
    csat_values = [r["csat"] for r in rows]
    csat_dist = {str(s): csat_values.count(s) for s in (5, 4, 3, 2, 1)}
    fast = [r["csat"] for r in rows if r["resolution_minutes"] <= 120]
    slow = [r["csat"] for r in rows if r["resolution_minutes"] > 300]
    # Escalation.
    esc = [r for r in rows if r["escalated"] == "yes"]
    non_esc = [r for r in rows if r["escalated"] != "yes"]
    results = {
        "total_incidents": total,
        "period": {
            "start": min(r["start_time"] for r in rows),
            "end": max(r["start_time"] for r in rows),
        },
        "overall_mttr_minutes": _mean([r["resolution_minutes"] for r in rows]),
        "overall_median_minutes": _median([r["resolution_minutes"] for r in rows]),
        "by_category": by_category,
        "by_severity": by_severity,
        "weekly_volume": [{"week_offset": w, "count": c} for w, c in weeks_sorted],
        "recurring_problems": recurring,
        "recurring_problem_count": len(recurring),
        "recurring_incident_share_pct": round(100 * recurring_incidents / total, 2),
        "csat": {
            "mean": _mean(csat_values),
            "distribution": csat_dist,
            "five_star_pct": round(100 * csat_dist["5"] / total, 2),
            "mean_resolution_le_120min": _mean(fast),
            "mean_resolution_gt_300min": _mean(slow),
        },
        "escalation": {
            "escalated_count": len(esc),
            "escalation_rate": round(len(esc) / total, 4),
            "mttr_escalated_minutes": _mean([r["resolution_minutes"] for r in esc]),
            "mttr_not_escalated_minutes": _mean([r["resolution_minutes"] for r in non_esc]),
        },
        "pipelines": dict(Counter(r["pipeline"] for r in rows)),
    }
    return results


def make_charts(results):
    os.makedirs(CHART_DIR, exist_ok=True)
    cats = CATEGORIES
    labels = [SHORT[c] for c in cats]
    colors = [COLORS[c] for c in cats]

    plt.figure(figsize=(8, 4.2))
    plt.bar(labels, [results["by_category"][c]["count"] for c in cats], color=colors)
    plt.title("Incidents by category (90 days, synthetic)")
    plt.ylabel("Incidents")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "incidents_by_category.png"), dpi=130)
    plt.close()

    plt.figure(figsize=(8, 4.2))
    plt.bar(labels, [results["by_category"][c]["mttr_minutes"] for c in cats], color=colors)
    plt.title("Mean time to resolve by category (minutes)")
    plt.ylabel("MTTR minutes")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "mttr_by_category.png"), dpi=130)
    plt.close()

    weeks = results["weekly_volume"]
    plt.figure(figsize=(8, 4.2))
    plt.plot([w["week_offset"] + 1 for w in weeks], [w["count"] for w in weeks],
             marker="o", color="#2563eb")
    plt.title("Incident volume by week")
    plt.xlabel("Week of the 90 day window")
    plt.ylabel("Incidents")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "volume_trend_weekly.png"), dpi=130)
    plt.close()

    dist = results["csat"]["distribution"]
    plt.figure(figsize=(8, 4.2))
    plt.bar(["5", "4", "3", "2", "1"], [dist[s] for s in ("5", "4", "3", "2", "1")],
            color="#059669")
    plt.title("CSAT score distribution")
    plt.xlabel("Score")
    plt.ylabel("Incidents")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "csat_distribution.png"), dpi=130)
    plt.close()

    sevs = SEVERITIES
    plt.figure(figsize=(8, 4.2))
    plt.bar(sevs, [results["by_severity"][s]["mttr_minutes"] for s in sevs], color="#7c3aed")
    plt.title("Mean time to resolve by severity (minutes)")
    plt.ylabel("MTTR minutes")
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "mttr_by_severity.png"), dpi=130)
    plt.close()


def write_findings(results):
    bc = results["by_category"]
    csat = results["csat"]
    esc = results["escalation"]
    top_recurring = results["recurring_problems"][:5]
    lines = [
        "# StreamGuard Findings",
        "",
        "All figures below are computed from the synthetic incident dataset in",
        "`data/incidents.csv` by `analysis/run_analysis.py`. The dataset is a",
        "simulation modeled on typical streaming data platform behavior; it is",
        "not production data from any company.",
        "",
        "## Headline numbers",
        "",
        f"- Total incidents in the 90 day window ({results['period']['start']} to {results['period']['end']}): **{results['total_incidents']}**",
        f"- Overall mean time to resolve (MTTR): **{results['overall_mttr_minutes']} minutes** (median {results['overall_median_minutes']} minutes)",
        f"- Mean CSAT: **{csat['mean']} out of 5**, with {csat['five_star_pct']}% of incidents rated 5",
        f"- Escalation rate: **{round(esc['escalation_rate'] * 100, 2)}%** ({esc['escalated_count']} of {results['total_incidents']} incidents)",
        "",
        "## Category breakdown",
        "",
        "| Category | Incidents | Share | MTTR (min) | Median (min) | CSAT mean | Escalation rate |",
        "|---|---|---|---|---|---|---|",
    ]
    for cat in CATEGORIES:
        s = bc[cat]
        lines.append(
            f"| {cat} | {s['count']} | {s['share_pct']}% | {s['mttr_minutes']} | "
            f"{s['median_minutes']} | {s['csat_mean']} | {round(s['escalation_rate'] * 100, 2)}% |"
        )
    lines += [
        "",
        "## What the numbers say",
        "",
        f"- Cluster Health Degradation is the slowest category to resolve at {bc['Cluster Health Degradation']['mttr_minutes']} minutes mean, "
        f"well above Configuration Error at {bc['Configuration Error']['mttr_minutes']} minutes, which matches operational intuition: "
        "node and disk problems need physical or infrastructure action, while configuration errors end with a rollback.",
        f"- Streaming Pipeline Failure is the most frequent category with {bc['Streaming Pipeline Failure']['count']} incidents "
        f"({bc['Streaming Pipeline Failure']['share_pct']}% of the total).",
        f"- Escalated incidents take much longer: {esc['mttr_escalated_minutes']} minutes mean versus {esc['mttr_not_escalated_minutes']} minutes "
        "for non-escalated ones, so escalation is a marker of genuinely hard incidents, not a shortcut.",
        f"- CSAT stays high but is resolution-time sensitive: incidents closed within 120 minutes average {csat['mean_resolution_le_120min']}, "
        f"while incidents taking over 300 minutes average {csat['mean_resolution_gt_300min']}.",
        "",
        "## Recurring problems",
        "",
        f"{results['recurring_problem_count']} root causes recur at least 15 times in the window and account for "
        f"{results['recurring_incident_share_pct']}% of all incidents. The top recurring root causes:",
        "",
    ]
    for item in top_recurring:
        lines.append(f"- {item['root_cause']}: {item['count']} incidents")
    lines += [
        "",
        "These are the candidates for permanent fixes: each recurring root cause",
        "that is engineered away removes its whole incident stream, which is a",
        "larger MTTR win than handling individual incidents faster.",
        "",
        "## Severity",
        "",
        "| Severity | Incidents | MTTR (min) | Escalation rate |",
        "|---|---|---|---|",
    ]
    for sev in SEVERITIES:
        s = results["by_severity"][sev]
        lines.append(
            f"| {sev} | {s['count']} | {s['mttr_minutes']} | {round(s['escalation_rate'] * 100, 2)}% |"
        )
    lines += [
        "",
        "## Charts",
        "",
        "- charts/incidents_by_category.png",
        "- charts/mttr_by_category.png",
        "- charts/volume_trend_weekly.png",
        "- charts/csat_distribution.png",
        "- charts/mttr_by_severity.png",
        "",
    ]
    path = os.path.join(os.path.dirname(__file__), "findings.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


def main():
    rows = load_incidents()
    results = analyze(rows)
    make_charts(results)
    out = os.path.join(ROOT, "output", "analysis_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(results, fh, indent=2)
    findings = write_findings(results)
    print(f"Incidents: {results['total_incidents']}")
    print(f"Overall MTTR: {results['overall_mttr_minutes']} min | CSAT mean: {results['csat']['mean']}")
    print(f"Wrote {out} and {findings}")


if __name__ == "__main__":
    main()
