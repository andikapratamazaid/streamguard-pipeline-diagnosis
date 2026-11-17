"""Build the self-contained StreamGuard dashboard HTML.

Reads the computed results (output/analysis_results.json,
output/evaluation_results.json, output/detection_results.json), embeds the
analysis charts as base64 images, and serializes the diagnosis engine's own
WEIGHTS, CAUSE_HINTS, and RESOLUTION_STEPS into the page so the interactive
demo in the browser runs the same rule logic as engine/diagnosis_engine.py.

    python3 dashboard/build_dashboard.py
"""

import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
from diagnosis_engine import WEIGHTS  # noqa: E402
from sg_common import (  # noqa: E402
    CATEGORIES,
    CAUSE_HINTS,
    RESOLUTION_STEPS,
    ROOT_CAUSES,
    SYMPTOMS,
)

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    with open(os.path.join(ROOT, "output", name)) as fh:
        return json.load(fh)


def _img64(relpath):
    with open(os.path.join(ROOT, relpath), "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def build():
    analysis = _load("analysis_results.json")
    evaluation = _load("evaluation_results.json")
    detection = _load("detection_results.json")

    charts = {
        "by_category": _img64("analysis/charts/incidents_by_category.png"),
        "mttr_category": _img64("analysis/charts/mttr_by_category.png"),
        "trend": _img64("analysis/charts/volume_trend_weekly.png"),
        "csat": _img64("analysis/charts/csat_distribution.png"),
        "mttr_severity": _img64("analysis/charts/mttr_by_severity.png"),
    }

    cat_rows = ""
    for cat in CATEGORIES:
        s = analysis["by_category"][cat]
        ev = evaluation["per_category"][cat]
        cat_rows += (
            f"<tr><td>{cat}</td><td>{s['count']}</td><td>{s['share_pct']}%</td>"
            f"<td>{s['mttr_minutes']}</td><td>{s['csat_mean']}</td>"
            f"<td>{round(s['escalation_rate'] * 100, 2)}%</td>"
            f"<td>{round(ev['accuracy'] * 100, 2)}%</td></tr>"
        )

    symptom_checks = ""
    for key, (label, _metric, _dir) in SYMPTOMS.items():
        symptom_checks += (
            f'<label class="sym"><input type="checkbox" value="{key}"> {label}</label>'
        )

    engine_json = json.dumps(
        {
            "weights": WEIGHTS,
            "causeHints": CAUSE_HINTS,
            "rootCauses": ROOT_CAUSES,
            "steps": RESOLUTION_STEPS,
            "categories": CATEGORIES,
        }
    )

    csat = analysis["csat"]
    esc = analysis["escalation"]
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>StreamGuard: Streaming Pipeline Reliability and Incident Diagnosis</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
  header {{ background: #1e293b; padding: 22px 28px; border-bottom: 3px solid #2563eb; }}
  header h1 {{ margin: 0; font-size: 24px; }}
  header p {{ margin: 6px 0 0; font-size: 13.5px; color: #94a3b8; max-width: 900px; }}
  .notice {{ background: #7c2d12; color: #fed7aa; padding: 10px 28px; font-size: 13px; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 22px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 22px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; }}
  .kpi .v {{ font-size: 26px; font-weight: 700; color: #fff; }}
  .kpi .l {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 18px; margin-bottom: 22px; }}
  section h2 {{ margin-top: 0; font-size: 17px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  th, td {{ border: 1px solid #334155; padding: 7px 9px; text-align: left; }}
  th {{ background: #0f172a; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 860px) {{ .charts {{ grid-template-columns: 1fr; }} }}
  .charts img {{ width: 100%; border-radius: 6px; background: #fff; }}
  .syms {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 8px; margin-bottom: 14px; }}
  .sym {{ background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 8px 10px; font-size: 13px; cursor: pointer; }}
  button {{ background: #2563eb; color: #fff; border: none; border-radius: 6px; padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer; }}
  #result {{ margin-top: 16px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 14px; display: none; }}
  #result h3 {{ margin: 0 0 6px; color: #fff; }}
  #result ol, #result ul {{ margin: 6px 0; padding-left: 20px; font-size: 13.5px; }}
  .muted {{ color: #94a3b8; font-size: 13px; }}
</style>
</head>
<body>
<header>
  <h1>StreamGuard: Streaming Pipeline Reliability and Incident Diagnosis</h1>
  <p>A data engineering support simulation: synthetic telemetry and incident data for six streaming pipelines over 90 days, a rule-based diagnosis engine, anomaly detection, and incident analytics across five problem categories.</p>
</header>
<div class="notice">SIMULATED DATA: every figure on this page is computed from a synthetic dataset generated for this case study. It is modeled on typical streaming data platform behavior and is not production data from any company.</div>
<div class="wrap">

  <div class="kpis">
    <div class="kpi"><div class="v">{analysis['total_incidents']}</div><div class="l">Total incidents resolved (90 days)</div></div>
    <div class="kpi"><div class="v">{analysis['overall_mttr_minutes']} min</div><div class="l">Overall MTTR (median {analysis['overall_median_minutes']} min)</div></div>
    <div class="kpi"><div class="v">{csat['mean']} / 5</div><div class="l">Mean CSAT ({csat['five_star_pct']}% rated 5)</div></div>
    <div class="kpi"><div class="v">{round(evaluation['overall_accuracy'] * 100, 2)}%</div><div class="l">Diagnosis engine accuracy ({evaluation['overall_correct']}/{evaluation['incidents_evaluated']})</div></div>
    <div class="kpi"><div class="v">{round(detection['detection_coverage'] * 100, 2)}%</div><div class="l">Anomaly detection coverage ({detection['incidents_detected']}/{detection['incidents_total']})</div></div>
    <div class="kpi"><div class="v">{round(esc['escalation_rate'] * 100, 2)}%</div><div class="l">Escalation rate ({esc['escalated_count']} incidents)</div></div>
  </div>

  <section>
    <h2>Category breakdown</h2>
    <table>
      <tr><th>Category</th><th>Incidents</th><th>Share</th><th>MTTR (min)</th><th>CSAT mean</th><th>Escalation rate</th><th>Engine accuracy</th></tr>
      {cat_rows}
    </table>
    <p class="muted">Cluster Health Degradation is the slowest category to resolve; Configuration Error is the fastest, because it usually ends with a rollback. Recurring root causes: {analysis['recurring_problem_count']} root causes occur 15 or more times and account for {analysis['recurring_incident_share_pct']}% of all incidents. Top recurring cause: {analysis['recurring_problems'][0]['root_cause']} ({analysis['recurring_problems'][0]['count']} incidents).</p>
  </section>

  <section>
    <h2>Charts</h2>
    <div class="charts">
      <img src="data:image/png;base64,{charts['by_category']}" alt="Incidents by category">
      <img src="data:image/png;base64,{charts['mttr_category']}" alt="MTTR by category">
      <img src="data:image/png;base64,{charts['trend']}" alt="Weekly incident volume">
      <img src="data:image/png;base64,{charts['csat']}" alt="CSAT distribution">
      <img src="data:image/png;base64,{charts['mttr_severity']}" alt="MTTR by severity">
    </div>
  </section>

  <section>
    <h2>Interactive diagnosis demo</h2>
    <p class="muted">Select the symptoms you observe, then run the diagnosis. This runs the same rule weights as the Python engine (engine/diagnosis_engine.py), reimplemented in JavaScript.</p>
    <div class="syms">{symptom_checks}</div>
    <button onclick="runDiagnosis()">Diagnose</button>
    <button onclick="clearSymptoms()" style="background:#475569">Clear</button>
    <div id="result"></div>
  </section>

  <p class="muted">StreamGuard case study. Data generation, engine, detection, and analytics are reproducible from the project repository with a fixed seed (42).</p>
</div>
<script>
const ENGINE = {engine_json};
function runDiagnosis() {{
  const checked = Array.from(document.querySelectorAll('.sym input:checked')).map(el => el.value);
  const box = document.getElementById('result');
  box.style.display = 'block';
  if (checked.length === 0) {{
    box.innerHTML = '<h3>No symptoms selected</h3><p class="muted">Select at least one symptom to run the diagnosis.</p>';
    return;
  }}
  const scores = {{}};
  ENGINE.categories.forEach(c => scores[c] = 0);
  checked.forEach(s => {{
    const w = ENGINE.weights[s] || {{}};
    Object.keys(w).forEach(c => scores[c] += w[c]);
  }});
  const ranked = Object.entries(scores).sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
  const top = ranked[0], second = ranked.length > 1 ? ranked[1] : ['none', 0];
  const total = Object.values(scores).reduce((a, b) => a + b, 0);
  const share = top[1] / total;
  const margin = top[1] ? (top[1] - second[1]) / top[1] : 0;
  let confidence = Math.min(0.99, 0.5 * share + 0.5 * margin + 0.25 * share);
  confidence = Math.max(confidence, share);
  const hints = ENGINE.causeHints[top[0]] || {{}};
  let causes = [];
  checked.forEach(s => {{ if (hints[s] && !causes.includes(hints[s])) causes.push(hints[s]); }});
  ENGINE.rootCauses[top[0]].forEach(c => {{ if (!causes.includes(c)) causes.push(c); }});
  causes = causes.slice(0, 2);
  const steps = ENGINE.steps[top[0]].map(s => '<li>' + s + '</li>').join('');
  const causeList = causes.map(c => '<li>' + c + '</li>').join('');
  const scoreList = ranked.map(r => r[0] + ': ' + r[1]).join(' | ');
  box.innerHTML = '<h3>Predicted category: ' + top[0] + '</h3>' +
    '<p>Confidence: ' + confidence.toFixed(2) + ' &nbsp;|&nbsp; Scores: ' + scoreList + '</p>' +
    '<p><strong>Likely root causes</strong></p><ul>' + causeList + '</ul>' +
    '<p><strong>Recommended resolution steps</strong></p><ol>' + steps + '</ol>';
}}
function clearSymptoms() {{
  document.querySelectorAll('.sym input:checked').forEach(el => el.checked = false);
  document.getElementById('result').style.display = 'none';
}}
</script>
</body>
</html>
"""
    out = os.path.join(os.path.dirname(__file__), "streamguard_dashboard.html")
    with open(out, "w") as fh:
        fh.write(html)
    print(f"Wrote {out} ({len(html)} bytes)")
    return out


if __name__ == "__main__":
    build()
