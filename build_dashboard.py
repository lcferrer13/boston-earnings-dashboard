#!/usr/bin/env python3
"""
Processes the 2025 Boston Employee Earnings Report CSV and generates
a self-contained interactive HTML dashboard with embedded data.
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).parent / "data" / "boston_earnings_2025.csv"
OUT_PATH = Path(__file__).parent / "index.html"


def parse_money(val: str) -> float:
    if not val or val.strip() == "":
        return 0.0
    return float(val.replace(",", "").replace('"', "").strip())


def load_data(path: str):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = {
                "name": row["NAME"].strip(),
                "dept": row["DEPARTMENT_NAME"].strip(),
                "title": row["TITLE"].strip(),
                "regular": parse_money(row["REGULAR"]),
                "retro": parse_money(row["RETRO"]),
                "other": parse_money(row["OTHER"]),
                "overtime": parse_money(row["OVERTIME"]),
                "injured": parse_money(row["INJURED"]),
                "detail": parse_money(row["DETAIL"]),
                "quinn": parse_money(row["QUINN_EDUCATION"]),
                "total": parse_money(row["TOTAL GROSS"]),
            }
            rows.append(r)
    return rows


def compute_stats(rows):
    stats = {}
    n = len(rows)
    totals = [r["total"] for r in rows]
    totals.sort(reverse=True)

    stats["employee_count"] = n
    stats["total_payroll"] = sum(totals)
    stats["median_pay"] = totals[n // 2]
    stats["mean_pay"] = stats["total_payroll"] / n
    stats["max_pay"] = totals[0]
    stats["top_1_pct_threshold"] = totals[int(n * 0.01)]
    stats["top_10_pct_threshold"] = totals[int(n * 0.10)]
    stats["total_overtime"] = sum(r["overtime"] for r in rows)
    stats["total_detail"] = sum(r["detail"] for r in rows)
    stats["total_quinn"] = sum(r["quinn"] for r in rows)
    stats["total_regular"] = sum(r["regular"] for r in rows)

    # Pay distribution histogram
    brackets = [0, 25000, 50000, 75000, 100000, 125000, 150000, 200000, 250000, 300000, 400000, 500000]
    hist = [0] * (len(brackets))
    for t in totals:
        placed = False
        for i in range(len(brackets) - 1):
            if t < brackets[i + 1]:
                hist[i] += 1
                placed = True
                break
        if not placed:
            hist[-1] += 1
    labels = []
    for i in range(len(brackets) - 1):
        labels.append(f"${brackets[i]//1000}K-${brackets[i+1]//1000}K")
    labels.append(f"${brackets[-1]//1000}K+")
    stats["pay_histogram"] = {"labels": labels, "counts": hist}

    # Department stats
    dept_data = defaultdict(lambda: {
        "count": 0, "total": 0, "overtime": 0, "detail": 0,
        "quinn": 0, "regular": 0, "other": 0, "injured": 0, "retro": 0
    })
    for r in rows:
        d = dept_data[r["dept"]]
        d["count"] += 1
        d["total"] += r["total"]
        d["overtime"] += r["overtime"]
        d["detail"] += r["detail"]
        d["quinn"] += r["quinn"]
        d["regular"] += r["regular"]
        d["other"] += r["other"]
        d["injured"] += r["injured"]
        d["retro"] += r["retro"]

    dept_list = []
    for name, d in dept_data.items():
        dept_list.append({
            "name": name,
            "count": d["count"],
            "total": round(d["total"]),
            "avg": round(d["total"] / d["count"]) if d["count"] > 0 else 0,
            "overtime": round(d["overtime"]),
            "detail": round(d["detail"]),
            "quinn": round(d["quinn"]),
            "regular": round(d["regular"]),
            "ot_pct": round(d["overtime"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        })
    dept_list.sort(key=lambda x: x["total"], reverse=True)
    stats["departments"] = dept_list[:40]

    # Top earners
    rows_sorted = sorted(rows, key=lambda x: x["total"], reverse=True)
    stats["top_earners"] = [
        {
            "name": r["name"], "dept": r["dept"], "title": r["title"],
            "total": round(r["total"]), "regular": round(r["regular"]),
            "overtime": round(r["overtime"]), "detail": round(r["detail"]),
            "quinn": round(r["quinn"]), "other": round(r["other"]),
        }
        for r in rows_sorted[:50]
    ]

    # OT warriors: people where OT > regular
    ot_warriors = [r for r in rows if r["overtime"] > r["regular"] and r["regular"] > 10000]
    ot_warriors.sort(key=lambda x: x["overtime"], reverse=True)
    stats["ot_warriors"] = [
        {
            "name": r["name"], "dept": r["dept"], "title": r["title"],
            "total": round(r["total"]), "regular": round(r["regular"]),
            "overtime": round(r["overtime"]),
            "ot_ratio": round(r["overtime"] / r["regular"], 2) if r["regular"] > 0 else 0,
        }
        for r in ot_warriors[:30]
    ]
    stats["ot_warrior_count"] = len(ot_warriors)

    # Police vs Fire vs Teachers vs Other comparison
    police = [r for r in rows if r["dept"] == "Boston Police Department"]
    fire = [r for r in rows if r["dept"] == "Boston Fire Department"]
    teachers = [r for r in rows if r["title"] == "Teacher"]
    paras = [r for r in rows if "Paraprofessional" in r["title"] or "Para" in r["title"]]
    subs = [r for r in rows if "Substitute" in r["title"]]
    cafeteria = [r for r in rows if "Cafeteria" in r["title"]]
    nurses = [r for r in rows if r["title"] == "Nurse"]

    def group_stats(group, label):
        if not group:
            return {"label": label, "count": 0, "avg_total": 0, "avg_regular": 0, "avg_overtime": 0, "avg_detail": 0, "total_payroll": 0}
        gross = sorted([r["total"] for r in group])
        return {
            "label": label,
            "count": len(group),
            "avg_total": round(sum(r["total"] for r in group) / len(group)),
            "median_total": round(gross[len(gross) // 2]),
            "avg_regular": round(sum(r["regular"] for r in group) / len(group)),
            "avg_overtime": round(sum(r["overtime"] for r in group) / len(group)),
            "avg_detail": round(sum(r["detail"] for r in group) / len(group)),
            "total_payroll": round(sum(r["total"] for r in group)),
        }

    stats["group_comparison"] = [
        group_stats(police, "Police"),
        group_stats(fire, "Firefighters"),
        group_stats(teachers, "Teachers"),
        group_stats(paras, "Paraprofessionals"),
        group_stats(nurses, "Nurses"),
        group_stats(subs, "Substitutes"),
        group_stats(cafeteria, "Cafeteria Workers"),
    ]

    # Payroll composition (what % is regular vs OT vs detail vs quinn vs other)
    stats["payroll_composition"] = {
        "regular": round(sum(r["regular"] for r in rows)),
        "overtime": round(sum(r["overtime"] for r in rows)),
        "detail": round(sum(r["detail"] for r in rows)),
        "quinn": round(sum(r["quinn"] for r in rows)),
        "other": round(sum(r["other"] for r in rows)),
        "retro": round(sum(r["retro"] for r in rows)),
        "injured": round(sum(r["injured"] for r in rows)),
    }

    # BPD detail pay breakdown by rank
    bpd_ranks = defaultdict(lambda: {"count": 0, "total": 0, "overtime": 0, "detail": 0, "quinn": 0, "regular": 0})
    for r in police:
        rank = r["title"]
        bpd_ranks[rank]["count"] += 1
        bpd_ranks[rank]["total"] += r["total"]
        bpd_ranks[rank]["overtime"] += r["overtime"]
        bpd_ranks[rank]["detail"] += r["detail"]
        bpd_ranks[rank]["quinn"] += r["quinn"]
        bpd_ranks[rank]["regular"] += r["regular"]

    bpd_rank_list = []
    for rank, d in bpd_ranks.items():
        if d["count"] >= 5:
            bpd_rank_list.append({
                "rank": rank,
                "count": d["count"],
                "avg_total": round(d["total"] / d["count"]),
                "avg_overtime": round(d["overtime"] / d["count"]),
                "avg_detail": round(d["detail"] / d["count"]),
                "avg_quinn": round(d["quinn"] / d["count"]),
                "avg_regular": round(d["regular"] / d["count"]),
            })
    bpd_rank_list.sort(key=lambda x: x["avg_total"], reverse=True)
    stats["bpd_ranks"] = bpd_rank_list[:15]

    # Department overtime concentration
    dept_ot = [d for d in stats["departments"] if d["overtime"] > 0]
    dept_ot.sort(key=lambda x: x["ot_pct"], reverse=True)
    stats["dept_ot_concentration"] = dept_ot[:15]

    # "200K Club" - how many people make 200K+ broken by dept
    over_200k = [r for r in rows if r["total"] >= 200000]
    over_200k_depts = Counter(r["dept"] for r in over_200k)
    stats["over_200k_count"] = len(over_200k)
    stats["over_200k_by_dept"] = [
        {"dept": dept, "count": count}
        for dept, count in over_200k_depts.most_common(15)
    ]

    # Ratio: police share of workforce vs share of payroll
    stats["police_share"] = {
        "headcount_pct": round(len(police) / n * 100, 1),
        "payroll_pct": round(sum(r["total"] for r in police) / stats["total_payroll"] * 100, 1),
        "overtime_pct": round(sum(r["overtime"] for r in police) / stats["total_overtime"] * 100, 1) if stats["total_overtime"] > 0 else 0,
        "detail_pct": round(sum(r["detail"] for r in police) / stats["total_detail"] * 100, 1) if stats["total_detail"] > 0 else 0,
    }
    stats["fire_share"] = {
        "headcount_pct": round(len(fire) / n * 100, 1),
        "payroll_pct": round(sum(r["total"] for r in fire) / stats["total_payroll"] * 100, 1),
        "overtime_pct": round(sum(r["overtime"] for r in fire) / stats["total_overtime"] * 100, 1) if stats["total_overtime"] > 0 else 0,
    }

    return stats


def build_html(stats):
    data_json = json.dumps(stats)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boston Employee Earnings 2025 — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

  :root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface2: #1a1a26;
    --border: #2a2a3a;
    --text: #e8e8f0;
    --text-dim: #8888a0;
    --accent: #6366f1;
    --accent2: #818cf8;
    --red: #ef4444;
    --orange: #f59e0b;
    --green: #22c55e;
    --cyan: #06b6d4;
    --pink: #ec4899;
    --purple: #a855f7;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}

  .container {{ max-width: 1400px; margin: 0 auto; padding: 0 24px; }}

  /* Hero */
  .hero {{
    padding: 80px 0 60px;
    text-align: center;
    background: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
    border-bottom: 1px solid var(--border);
  }}
  .hero h1 {{
    font-size: 3.2rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #e8e8f0 0%, #6366f1 50%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 12px;
  }}
  .hero .subtitle {{
    font-size: 1.15rem;
    color: var(--text-dim);
    font-weight: 400;
    max-width: 650px;
    margin: 0 auto 48px;
  }}

  /* Stat cards */
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 0 auto;
    max-width: 1200px;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    text-align: center;
  }}
  .stat-card .label {{ font-size: 0.78rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; margin-bottom: 8px; }}
  .stat-card .value {{ font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; }}
  .stat-card .sub {{ font-size: 0.82rem; color: var(--text-dim); margin-top: 4px; }}
  .stat-card.accent .value {{ color: var(--accent2); }}
  .stat-card.red .value {{ color: var(--red); }}
  .stat-card.orange .value {{ color: var(--orange); }}
  .stat-card.green .value {{ color: var(--green); }}
  .stat-card.cyan .value {{ color: var(--cyan); }}
  .stat-card.pink .value {{ color: var(--pink); }}

  /* Sections */
  .section {{
    padding: 64px 0;
    border-bottom: 1px solid var(--border);
  }}
  .section-header {{
    margin-bottom: 32px;
  }}
  .section-header h2 {{
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 8px;
  }}
  .section-header .section-sub {{
    font-size: 0.95rem;
    color: var(--text-dim);
    max-width: 700px;
  }}
  .section-header .insight {{
    display: inline-block;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 8px;
    padding: 12px 18px;
    margin-top: 16px;
    font-size: 0.9rem;
    color: var(--accent2);
    line-height: 1.5;
  }}
  .section-header .insight.red {{
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.25);
    color: #fca5a5;
  }}
  .section-header .insight.orange {{
    background: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.25);
    color: #fcd34d;
  }}

  /* Charts */
  .chart-container {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
  }}
  .chart-container h3 {{
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--text-dim);
  }}
  .chart-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  @media (max-width: 900px) {{
    .chart-row {{ grid-template-columns: 1fr; }}
  }}

  /* Tables */
  .data-table-wrap {{
    overflow-x: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 24px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }}
  th {{
    text-align: left;
    padding: 12px 16px;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.72rem;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--surface);
  }}
  th.right, td.right {{ text-align: right; }}
  td {{
    padding: 10px 16px;
    border-bottom: 1px solid rgba(42, 42, 58, 0.5);
    white-space: nowrap;
  }}
  tr:hover td {{ background: rgba(99, 102, 241, 0.04); }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .badge-red {{ background: rgba(239,68,68,0.15); color: #fca5a5; }}
  .badge-orange {{ background: rgba(245,158,11,0.15); color: #fcd34d; }}
  .badge-green {{ background: rgba(34,197,94,0.15); color: #86efac; }}
  .badge-blue {{ background: rgba(99,102,241,0.15); color: #a5b4fc; }}

  /* Comparison bars */
  .compare-row {{
    display: flex;
    align-items: center;
    margin-bottom: 14px;
    gap: 12px;
  }}
  .compare-label {{
    width: 140px;
    font-size: 0.85rem;
    font-weight: 500;
    flex-shrink: 0;
  }}
  .compare-bar-wrap {{
    flex: 1;
    background: var(--surface2);
    border-radius: 6px;
    height: 32px;
    position: relative;
    overflow: hidden;
  }}
  .compare-bar {{
    height: 100%;
    border-radius: 6px;
    display: flex;
    align-items: center;
    padding-left: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    color: white;
    transition: width 0.8s ease;
  }}
  .compare-value {{
    font-size: 0.85rem;
    font-weight: 600;
    width: 100px;
    text-align: right;
    flex-shrink: 0;
  }}

  /* Callout boxes */
  .callout {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 24px;
  }}
  .callout h3 {{
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 16px;
  }}
  .callout-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 20px;
  }}
  .callout-stat .num {{ font-size: 2rem; font-weight: 800; }}
  .callout-stat .desc {{ font-size: 0.82rem; color: var(--text-dim); margin-top: 2px; }}

  /* Stacked bar */
  .stacked-bar {{
    display: flex;
    height: 40px;
    border-radius: 8px;
    overflow: hidden;
    margin: 16px 0;
  }}
  .stacked-bar div {{
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 600;
    color: white;
    transition: flex 0.5s;
  }}
  .legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-top: 12px;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
    color: var(--text-dim);
  }}
  .legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 3px;
  }}

  .footer {{
    text-align: center;
    padding: 40px 0;
    color: var(--text-dim);
    font-size: 0.82rem;
  }}
  .footer a {{ color: var(--accent2); text-decoration: none; }}

  .highlight {{ color: var(--accent2); font-weight: 700; }}
  .highlight-red {{ color: var(--red); font-weight: 700; }}
  .highlight-orange {{ color: var(--orange); font-weight: 700; }}
</style>
</head>
<body>

<script>
const DATA = {data_json};
</script>

<!-- ===== HERO ===== -->
<div class="hero">
  <div class="container">
    <h1>Boston City Payroll</h1>
    <p class="subtitle">A data-driven look at how $2.46 billion in taxpayer money was distributed across 25,397 city employees in 2025</p>
    <div class="stat-grid">
      <div class="stat-card accent">
        <div class="label">Total Payroll</div>
        <div class="value" id="hero-payroll"></div>
        <div class="sub">Fiscal Year 2025</div>
      </div>
      <div class="stat-card green">
        <div class="label">Employees</div>
        <div class="value" id="hero-employees"></div>
        <div class="sub">across 228 departments</div>
      </div>
      <div class="stat-card cyan">
        <div class="label">Median Pay</div>
        <div class="value" id="hero-median"></div>
        <div class="sub" id="hero-mean-sub"></div>
      </div>
      <div class="stat-card orange">
        <div class="label">Overtime Paid</div>
        <div class="value" id="hero-overtime"></div>
        <div class="sub" id="hero-ot-sub"></div>
      </div>
      <div class="stat-card pink">
        <div class="label">Highest Earner</div>
        <div class="value" id="hero-max"></div>
        <div class="sub" id="hero-max-sub"></div>
      </div>
      <div class="stat-card red">
        <div class="label">$200K+ Club</div>
        <div class="value" id="hero-200k"></div>
        <div class="sub" id="hero-200k-sub"></div>
      </div>
    </div>
  </div>
</div>

<!-- ===== 1. PAY DISTRIBUTION ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>Where Does the Money Go?</h2>
      <p class="section-sub">The $2.46 billion payroll is not just base salaries. Overtime, detail assignments, education incentives, and other supplemental pay dramatically reshape who earns what.</p>
    </div>
    <div class="chart-row">
      <div class="chart-container">
        <h3>Payroll Composition — $2.46B breakdown</h3>
        <canvas id="compositionChart" height="280"></canvas>
      </div>
      <div class="chart-container">
        <h3>Gross Pay Distribution — 25,397 employees</h3>
        <canvas id="histogramChart" height="280"></canvas>
      </div>
    </div>
  </div>
</div>

<!-- ===== 2. POLICE & FIRE DOMINANCE ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>The Public Safety Premium</h2>
      <p class="section-sub">Boston Police and Fire together account for 19% of the city's workforce but take home 35% of all pay. The gap is driven by overtime, "detail" pay (private companies paying officers for security), and Quinn Bill education incentives.</p>
      <div class="insight red">Police are <strong id="bpd-headcount-pct"></strong> of employees but collect <strong id="bpd-payroll-pct"></strong> of payroll, <strong id="bpd-ot-pct"></strong> of all overtime, and <strong id="bpd-detail-pct"></strong> of all detail pay.</div>
    </div>

    <div class="callout">
      <h3>Workforce Share vs. Payroll Share</h3>
      <div id="share-bars"></div>
    </div>

    <div class="chart-row">
      <div class="chart-container">
        <h3>Average Total Compensation by Group</h3>
        <canvas id="groupAvgChart" height="300"></canvas>
      </div>
      <div class="chart-container">
        <h3>Where Police Pay Comes From (by Rank)</h3>
        <canvas id="bpdRankChart" height="300"></canvas>
      </div>
    </div>
  </div>
</div>

<!-- ===== 3. OVERTIME MACHINE ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>The Overtime Machine</h2>
      <p class="section-sub">$183 million in overtime was paid in 2025. Some employees earned more in overtime alone than their entire base salary — effectively doubling or tripling their pay.</p>
      <div class="insight orange">There are <strong id="ot-warrior-count"></strong> employees whose overtime exceeded their base salary (with base &gt; $10K). The top overtime earner collected <strong id="ot-warrior-top"></strong> in OT on a base of <strong id="ot-warrior-top-base"></strong>.</div>
    </div>

    <div class="chart-container">
      <h3>Overtime Concentration by Department (as % of total department pay)</h3>
      <canvas id="otDeptChart" height="350"></canvas>
    </div>

    <div class="data-table-wrap" style="max-height: 500px; overflow-y: auto;">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Title</th>
            <th class="right">Base Pay</th>
            <th class="right">Overtime</th>
            <th class="right">OT / Base Ratio</th>
            <th class="right">Total Gross</th>
          </tr>
        </thead>
        <tbody id="ot-warriors-table"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ===== 4. THE $200K CLUB ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>The $200K Club</h2>
      <p class="section-sub">Over <span id="club-count" class="highlight"></span> city employees earned $200,000 or more. The vast majority are in public safety — but not all are chiefs or commissioners.</p>
    </div>
    <div class="chart-row">
      <div class="chart-container">
        <h3>$200K+ Employees by Department</h3>
        <canvas id="club200kChart" height="350"></canvas>
      </div>
      <div class="chart-container">
        <h3>Top 15 Departments — Avg Total Compensation</h3>
        <canvas id="deptAvgChart" height="350"></canvas>
      </div>
    </div>
  </div>
</div>

<!-- ===== 5. TOP EARNERS TABLE ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>Highest-Paid City Employees</h2>
      <p class="section-sub">The top 50 earners in Boston city government. Notice how supplemental pay — overtime, detail, and Quinn education bonuses — pushes many well beyond their base salary.</p>
    </div>
    <div class="data-table-wrap" style="max-height: 700px; overflow-y: auto;">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Department</th>
            <th>Title</th>
            <th class="right">Base</th>
            <th class="right">Overtime</th>
            <th class="right">Detail</th>
            <th class="right">Quinn Ed.</th>
            <th class="right">Other</th>
            <th class="right">Total</th>
          </tr>
        </thead>
        <tbody id="top-earners-table"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ===== 6. DEPARTMENT DEEP DIVE ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>Department Landscape</h2>
      <p class="section-sub">How the city's 228 departments compare in headcount and pay. Bubble size shows total payroll spend.</p>
    </div>
    <div class="chart-container">
      <h3>Headcount vs. Average Pay (top 25 departments)</h3>
      <canvas id="deptScatterChart" height="420"></canvas>
    </div>
  </div>
</div>

<!-- ===== 7. TEACHER COMPARISON ===== -->
<div class="section">
  <div class="container">
    <div class="section-header">
      <h2>Who Serves, Who Earns?</h2>
      <p class="section-sub">Boston's teachers, paraprofessionals, nurses, and cafeteria workers keep the school system running — but their compensation tells a different story than public safety.</p>
    </div>
    <div class="callout">
      <h3>Head-to-Head: Median Total Compensation</h3>
      <div id="comparison-bars"></div>
    </div>

    <div class="chart-container">
      <h3>Compensation Breakdown by Group</h3>
      <canvas id="groupStackChart" height="320"></canvas>
    </div>
  </div>
</div>


<div class="footer">
  <div class="container">
    <p>Data: City of Boston Employee Earnings Report, 2025 &bull; Built by <a href="#">Lucas Ferrer</a> at the Berkman Klein Center at Harvard</p>
    <p style="margin-top:8px;">Dashboard auto-generated from public payroll data. All figures represent gross pay.</p>
  </div>
</div>

<script>
// ─── Utilities ───────────────────────────────────────
const fmt = n => '$' + n.toLocaleString('en-US');
const fmtM = n => '$' + (n / 1e6).toFixed(1) + 'M';
const fmtB = n => '$' + (n / 1e9).toFixed(2) + 'B';
const fmtK = n => '$' + (n / 1e3).toFixed(0) + 'K';
const pct = (a, b) => ((a / b) * 100).toFixed(1) + '%';

Chart.defaults.color = '#8888a0';
Chart.defaults.borderColor = 'rgba(42,42,58,0.5)';
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

// ─── Hero Stats ──────────────────────────────────────
document.getElementById('hero-payroll').textContent = fmtB(DATA.total_payroll);
document.getElementById('hero-employees').textContent = DATA.employee_count.toLocaleString();
document.getElementById('hero-median').textContent = fmtK(DATA.median_pay);
document.getElementById('hero-mean-sub').textContent = 'Mean: ' + fmtK(DATA.mean_pay);
document.getElementById('hero-overtime').textContent = fmtM(DATA.total_overtime);
document.getElementById('hero-ot-sub').textContent = pct(DATA.total_overtime, DATA.total_payroll) + ' of payroll';
document.getElementById('hero-max').textContent = fmtK(DATA.max_pay);
document.getElementById('hero-max-sub').textContent = DATA.top_earners[0].name.split(',').reverse().join(' ').trim();
document.getElementById('hero-200k').textContent = DATA.over_200k_count.toLocaleString();
document.getElementById('hero-200k-sub').textContent = pct(DATA.over_200k_count, DATA.employee_count) + ' of workforce';

// ─── Payroll Composition Donut ───────────────────────
const comp = DATA.payroll_composition;
new Chart(document.getElementById('compositionChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['Base Salary', 'Overtime', 'Detail', 'Quinn Education', 'Other', 'Retro', 'Injured'],
    datasets: [{{
      data: [comp.regular, comp.overtime, comp.detail, comp.quinn, comp.other, comp.retro, comp.injured],
      backgroundColor: ['#6366f1', '#ef4444', '#f59e0b', '#a855f7', '#06b6d4', '#22c55e', '#64748b'],
      borderWidth: 0,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'right', labels: {{ padding: 12, usePointStyle: true, pointStyle: 'rectRounded' }} }},
      tooltip: {{ callbacks: {{ label: ctx => ctx.label + ': ' + fmtM(ctx.raw) + ' (' + pct(ctx.raw, DATA.total_payroll) + ')' }} }}
    }}
  }}
}});

// ─── Pay Histogram ───────────────────────────────────
new Chart(document.getElementById('histogramChart'), {{
  type: 'bar',
  data: {{
    labels: DATA.pay_histogram.labels,
    datasets: [{{
      data: DATA.pay_histogram.counts,
      backgroundColor: DATA.pay_histogram.counts.map((_, i) => {{
        const colors = ['#22c55e','#22c55e','#06b6d4','#06b6d4','#6366f1','#6366f1','#a855f7','#a855f7','#f59e0b','#f59e0b','#ef4444','#ef4444'];
        return colors[i] || '#ef4444';
      }}),
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => ctx.raw.toLocaleString() + ' employees' }} }} }},
    scales: {{
      y: {{ grid: {{ color: 'rgba(42,42,58,0.3)' }}, title: {{ display: true, text: 'Employees' }} }},
      x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
    }}
  }}
}});

// ─── Police Share Section ────────────────────────────
document.getElementById('bpd-headcount-pct').textContent = DATA.police_share.headcount_pct + '%';
document.getElementById('bpd-payroll-pct').textContent = DATA.police_share.payroll_pct + '%';
document.getElementById('bpd-ot-pct').textContent = DATA.police_share.overtime_pct + '%';
document.getElementById('bpd-detail-pct').textContent = DATA.police_share.detail_pct + '%';

// Share bars
const shareData = [
  {{ label: 'Police', headcount: DATA.police_share.headcount_pct, payroll: DATA.police_share.payroll_pct, color: '#ef4444' }},
  {{ label: 'Fire', headcount: DATA.fire_share.headcount_pct, payroll: DATA.fire_share.payroll_pct, color: '#f59e0b' }},
  {{ label: 'All Others', headcount: (100 - DATA.police_share.headcount_pct - DATA.fire_share.headcount_pct).toFixed(1), payroll: (100 - DATA.police_share.payroll_pct - DATA.fire_share.payroll_pct).toFixed(1), color: '#6366f1' }},
];
let shareBarsHTML = `
<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 16px;">
<div>
  <div style="font-size:0.78rem; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.06em; font-weight:600; margin-bottom:12px;">% of Workforce</div>
  <div class="stacked-bar">` +
    shareData.map(s => `<div style="flex:${{s.headcount}};background:${{s.color}}">${{s.headcount}}%</div>`).join('') +
  `</div>
</div>
<div>
  <div style="font-size:0.78rem; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.06em; font-weight:600; margin-bottom:12px;">% of Payroll</div>
  <div class="stacked-bar">` +
    shareData.map(s => `<div style="flex:${{s.payroll}};background:${{s.color}}">${{s.payroll}}%</div>`).join('') +
  `</div>
</div></div>
<div class="legend" style="margin-top:16px;">` +
    shareData.map(s => `<div class="legend-item"><div class="legend-dot" style="background:${{s.color}}"></div>${{s.label}}</div>`).join('') +
`</div>`;
document.getElementById('share-bars').innerHTML = shareBarsHTML;

// ─── Group Avg Chart ─────────────────────────────────
const groups = DATA.group_comparison;
new Chart(document.getElementById('groupAvgChart'), {{
  type: 'bar',
  data: {{
    labels: groups.map(g => g.label),
    datasets: [
      {{ label: 'Base Salary', data: groups.map(g => g.avg_regular), backgroundColor: '#6366f1', borderRadius: 4 }},
      {{ label: 'Overtime', data: groups.map(g => g.avg_overtime), backgroundColor: '#ef4444', borderRadius: 4 }},
      {{ label: 'Detail', data: groups.map(g => g.avg_detail), backgroundColor: '#f59e0b', borderRadius: 4 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'top', labels: {{ usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }} }},
      tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + fmt(ctx.raw) }} }}
    }},
    scales: {{
      x: {{ stacked: true, grid: {{ display: false }} }},
      y: {{ stacked: true, grid: {{ color: 'rgba(42,42,58,0.3)' }}, ticks: {{ callback: v => fmtK(v) }} }}
    }}
  }}
}});

// ─── BPD Rank Chart ──────────────────────────────────
const bpdRanks = DATA.bpd_ranks.slice(0, 10);
new Chart(document.getElementById('bpdRankChart'), {{
  type: 'bar',
  data: {{
    labels: bpdRanks.map(r => r.rank.replace('Police ', '').replace('Lieut-Hackney Carriage Inves.', 'Lt-Hackney Inv.')),
    datasets: [
      {{ label: 'Base', data: bpdRanks.map(r => r.avg_regular), backgroundColor: '#6366f1', borderRadius: 2 }},
      {{ label: 'Overtime', data: bpdRanks.map(r => r.avg_overtime), backgroundColor: '#ef4444', borderRadius: 2 }},
      {{ label: 'Detail', data: bpdRanks.map(r => r.avg_detail), backgroundColor: '#f59e0b', borderRadius: 2 }},
      {{ label: 'Quinn', data: bpdRanks.map(r => r.avg_quinn), backgroundColor: '#a855f7', borderRadius: 2 }},
    ]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{
      legend: {{ position: 'top', labels: {{ usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }} }},
      tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + fmt(ctx.raw) }} }}
    }},
    scales: {{
      x: {{ stacked: true, grid: {{ color: 'rgba(42,42,58,0.3)' }}, ticks: {{ callback: v => fmtK(v) }} }},
      y: {{ stacked: true, grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
    }}
  }}
}});

// ─── OT Section ──────────────────────────────────────
document.getElementById('ot-warrior-count').textContent = DATA.ot_warrior_count;
if (DATA.ot_warriors.length > 0) {{
  document.getElementById('ot-warrior-top').textContent = fmt(DATA.ot_warriors[0].overtime);
  document.getElementById('ot-warrior-top-base').textContent = fmt(DATA.ot_warriors[0].regular);
}}

// OT Dept chart
const otDepts = DATA.dept_ot_concentration.filter(d => d.overtime > 500000);
new Chart(document.getElementById('otDeptChart'), {{
  type: 'bar',
  data: {{
    labels: otDepts.map(d => d.name.length > 30 ? d.name.slice(0, 28) + '…' : d.name),
    datasets: [
      {{ label: 'Overtime ($)', data: otDepts.map(d => d.overtime), backgroundColor: '#ef4444', borderRadius: 4, yAxisID: 'y' }},
      {{ label: 'OT as % of Dept Pay', data: otDepts.map(d => d.ot_pct), backgroundColor: '#f59e0b88', borderRadius: 4, yAxisID: 'y1', type: 'line', borderColor: '#f59e0b', pointBackgroundColor: '#f59e0b', tension: 0.3 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'top', labels: {{ usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }} }},
      tooltip: {{ callbacks: {{ label: ctx => ctx.datasetIndex === 0 ? fmtM(ctx.raw) : ctx.raw + '%' }} }}
    }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }}, maxRotation: 45 }} }},
      y: {{ position: 'left', grid: {{ color: 'rgba(42,42,58,0.3)' }}, ticks: {{ callback: v => fmtM(v) }}, title: {{ display: true, text: 'Overtime $' }} }},
      y1: {{ position: 'right', grid: {{ display: false }}, ticks: {{ callback: v => v + '%' }}, title: {{ display: true, text: '% of Dept Pay' }}, min: 0 }}
    }}
  }}
}});

// OT Warriors table
const otTbody = document.getElementById('ot-warriors-table');
DATA.ot_warriors.forEach(w => {{
  const ratioBadge = w.ot_ratio >= 2 ? 'badge-red' : w.ot_ratio >= 1.5 ? 'badge-orange' : 'badge-green';
  otTbody.innerHTML += `<tr>
    <td>${{w.name}}</td>
    <td>${{w.title}}</td>
    <td class="right">${{fmt(w.regular)}}</td>
    <td class="right" style="color:#ef4444;font-weight:600">${{fmt(w.overtime)}}</td>
    <td class="right"><span class="badge ${{ratioBadge}}">${{w.ot_ratio}}x</span></td>
    <td class="right" style="font-weight:600">${{fmt(w.total)}}</td>
  </tr>`;
}});

// ─── $200K Club ──────────────────────────────────────
document.getElementById('club-count').textContent = DATA.over_200k_count.toLocaleString();
const club = DATA.over_200k_by_dept;
new Chart(document.getElementById('club200kChart'), {{
  type: 'bar',
  data: {{
    labels: club.map(d => d.dept.length > 28 ? d.dept.slice(0, 26) + '…' : d.dept),
    datasets: [{{
      data: club.map(d => d.count),
      backgroundColor: club.map((_, i) => i < 2 ? '#ef4444' : '#6366f1'),
      borderRadius: 4,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => ctx.raw + ' employees' }} }} }},
    scales: {{
      x: {{ grid: {{ color: 'rgba(42,42,58,0.3)' }}, title: {{ display: true, text: 'Employees earning $200K+' }} }},
      y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }}
    }}
  }}
}});

// Dept avg chart (top 15)
const deptTop = DATA.departments.slice(0, 15);
new Chart(document.getElementById('deptAvgChart'), {{
  type: 'bar',
  data: {{
    labels: deptTop.map(d => d.name.length > 28 ? d.name.slice(0, 26) + '…' : d.name),
    datasets: [{{
      label: 'Average Total Comp',
      data: deptTop.map(d => d.avg),
      backgroundColor: deptTop.map(d => d.avg > 150000 ? '#ef4444' : d.avg > 100000 ? '#f59e0b' : '#6366f1'),
      borderRadius: 4,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{ label: ctx => fmt(ctx.raw) + ' avg (' + deptTop[ctx.dataIndex].count + ' emp)' }} }} }},
    scales: {{
      x: {{ grid: {{ color: 'rgba(42,42,58,0.3)' }}, ticks: {{ callback: v => fmtK(v) }} }},
      y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
    }}
  }}
}});

// ─── Top Earners Table ───────────────────────────────
const teTbody = document.getElementById('top-earners-table');
DATA.top_earners.forEach((e, i) => {{
  const otPct = e.regular > 0 ? ((e.overtime / e.regular) * 100).toFixed(0) : 0;
  teTbody.innerHTML += `<tr>
    <td style="color:var(--text-dim)">${{i + 1}}</td>
    <td style="font-weight:600">${{e.name}}</td>
    <td>${{e.dept.length > 25 ? e.dept.slice(0, 23) + '…' : e.dept}}</td>
    <td>${{e.title}}</td>
    <td class="right">${{fmt(e.regular)}}</td>
    <td class="right" style="color:${{e.overtime > e.regular ? '#ef4444' : 'inherit'}}">${{e.overtime > 0 ? fmt(e.overtime) : '—'}}</td>
    <td class="right" style="color:${{e.detail > 50000 ? '#f59e0b' : 'inherit'}}">${{e.detail > 0 ? fmt(e.detail) : '—'}}</td>
    <td class="right">${{e.quinn > 0 ? fmt(e.quinn) : '—'}}</td>
    <td class="right">${{e.other > 0 ? fmt(e.other) : '—'}}</td>
    <td class="right" style="font-weight:700">${{fmt(e.total)}}</td>
  </tr>`;
}});

// ─── Dept Scatter / Bubble ───────────────────────────
const deptBubble = DATA.departments.slice(0, 25);
const maxTotal = Math.max(...deptBubble.map(d => d.total));
new Chart(document.getElementById('deptScatterChart'), {{
  type: 'bubble',
  data: {{
    datasets: deptBubble.map((d, i) => ({{
      label: d.name,
      data: [{{ x: d.count, y: d.avg, r: Math.max(4, Math.sqrt(d.total / maxTotal) * 45) }}],
      backgroundColor: d.name.includes('Police') ? 'rgba(239,68,68,0.6)' :
                        d.name.includes('Fire') ? 'rgba(245,158,11,0.6)' :
                        d.name.includes('School') || d.name.includes('Education') || d.name.includes('Teacher') || d.name.includes('BPS') ? 'rgba(34,197,94,0.6)' :
                        'rgba(99,102,241,0.5)',
      borderColor: 'transparent',
    }}))
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{
        label: ctx => {{
          const d = deptBubble[ctx.datasetIndex];
          return [d.name, `${{d.count}} employees`, `Avg: ${{fmtK(d.avg)}}`, `Total: ${{fmtM(d.total)}}`];
        }}
      }} }}
    }},
    scales: {{
      x: {{ grid: {{ color: 'rgba(42,42,58,0.3)' }}, title: {{ display: true, text: 'Number of Employees' }} }},
      y: {{ grid: {{ color: 'rgba(42,42,58,0.3)' }}, ticks: {{ callback: v => fmtK(v) }}, title: {{ display: true, text: 'Average Total Compensation' }} }}
    }}
  }}
}});

// ─── Comparison Bars ─────────────────────────────────
const maxMedian = Math.max(...groups.map(g => g.median_total));
let compHTML = '';
const barColors = ['#ef4444', '#f59e0b', '#6366f1', '#22c55e', '#06b6d4', '#a855f7', '#64748b'];
groups.forEach((g, i) => {{
  const w = (g.median_total / maxMedian * 100).toFixed(1);
  compHTML += `<div class="compare-row">
    <div class="compare-label">${{g.label}}</div>
    <div class="compare-bar-wrap">
      <div class="compare-bar" style="width:${{w}}%;background:${{barColors[i]}}">${{g.count.toLocaleString()}} emp</div>
    </div>
    <div class="compare-value">${{fmtK(g.median_total)}}</div>
  </div>`;
}});
document.getElementById('comparison-bars').innerHTML = compHTML;

// ─── Group Stacked Chart ─────────────────────────────
new Chart(document.getElementById('groupStackChart'), {{
  type: 'bar',
  data: {{
    labels: groups.map(g => g.label + ' (' + g.count.toLocaleString() + ')'),
    datasets: [
      {{ label: 'Total Payroll ($)', data: groups.map(g => g.total_payroll), backgroundColor: barColors, borderRadius: 4 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: ctx => fmtM(ctx.raw) + ' total payroll for ' + groups[ctx.dataIndex].count.toLocaleString() + ' employees' }} }}
    }},
    scales: {{
      x: {{ grid: {{ display: false }} }},
      y: {{ grid: {{ color: 'rgba(42,42,58,0.3)' }}, ticks: {{ callback: v => fmtM(v) }} }}
    }}
  }}
}});
</script>

</body>
</html>"""


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(CSV_PATH)
    print(f"Loading data from {csv_path}...")
    rows = load_data(csv_path)
    print(f"Loaded {len(rows)} employees.")

    print("Computing statistics...")
    stats = compute_stats(rows)

    html = build_html(stats)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html)
    print(f"Dashboard written to {OUT_PATH}")
    print(f"Open in browser: file://{OUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
