"""Generate visualizations and markdown summary from analytics output."""

import os
import sqlite3
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_csv(reports_dir, name):
    path = os.path.join(reports_dir, "data", f"{name}.csv")
    return pd.read_csv(path)


def plot_failure_heatmap(reports_dir, figures_dir):
    df = _load_csv(reports_dir, "failure_rate_heatmap")
    pivot = df.pivot_table(
        index="part_category", columns="engine_model",
        values="failure_count", aggfunc="sum", fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(pivot, annot=True, fmt="d", cmap="YlOrRd", linewidths=0.5, ax=ax)
    ax.set_title("Failure Count by Engine Model × Part Category")
    ax.set_ylabel("Part Category")
    ax.set_xlabel("Engine Model")
    plt.tight_layout()
    fig.savefig(os.path.join(figures_dir, "failure_heatmap.png"), dpi=150)
    plt.close(fig)


def plot_monthly_cost_trend(reports_dir, figures_dir):
    df = _load_csv(reports_dir, "maintenance_cost_forecast")
    df["month"] = pd.to_datetime(df["month"])

    fig, ax = plt.subplots(figsize=(12, 6))
    for model, group in df.groupby("engine_model"):
        actual = group[group["monthly_cost"].notna()]
        forecast = group[group["monthly_cost"].isna()]
        ax.plot(actual["month"], actual["rolling_6m_avg"], label=f"{model} (rolling avg)")
        if not forecast.empty:
            combined = pd.concat([actual.tail(1), forecast])
            ax.plot(combined["month"], combined["rolling_6m_avg"],
                    linestyle="--", alpha=0.7, label=f"{model} (forecast)")

    ax.set_title("Monthly Maintenance Cost — 6-Month Rolling Average with Forecast")
    ax.set_xlabel("Month")
    ax.set_ylabel("Cost (USD)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    fig.savefig(os.path.join(figures_dir, "monthly_cost_trend.png"), dpi=150)
    plt.close(fig)


def plot_fleet_availability(reports_dir, figures_dir):
    df = _load_csv(reports_dir, "fleet_availability_score")
    df["month"] = pd.to_datetime(df["month"])

    fig, ax = plt.subplots(figsize=(12, 6))
    pivot = df.pivot_table(index="month", columns="fleet", values="availability_pct")
    pivot.plot(kind="bar", stacked=False, ax=ax, width=0.7)
    ax.set_title("Fleet Availability Score by Month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Availability %")
    ax.set_ylim(0, 105)
    ax.legend(title="Fleet")
    ax.grid(True, axis="y", alpha=0.3)

    ticks = ax.get_xticks()
    step = max(1, len(ticks) // 12)
    ax.set_xticks(ticks[::step])
    labels = [t.strftime("%Y-%m") for t in pivot.index[::step]]
    ax.set_xticklabels(labels, rotation=45)

    plt.tight_layout()
    fig.savefig(os.path.join(figures_dir, "fleet_availability.png"), dpi=150)
    plt.close(fig)


def plot_anomaly_scatter(reports_dir, figures_dir):
    df = _load_csv(reports_dir, "anomaly_detection_flags")

    fig, ax = plt.subplots(figsize=(10, 7))
    scatter = ax.scatter(
        df["mean_time_between_failure_hours"],
        df["flight_hours_at_replacement"],
        c=df["severity_score"],
        cmap="RdYlGn_r",
        alpha=0.6,
        edgecolors="gray",
        linewidth=0.3,
        s=30,
    )
    # Reference line: 50% MTBF threshold
    max_mtbf = df["mean_time_between_failure_hours"].max()
    ax.plot([0, max_mtbf], [0, max_mtbf * 0.5], "r--", alpha=0.5, label="50% MTBF threshold")

    ax.set_title("Premature Failure Flags — Hours at Replacement vs. MTBF")
    ax.set_xlabel("Catalog MTBF (hours)")
    ax.set_ylabel("Flight Hours at Replacement")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label="Severity Score")
    plt.tight_layout()
    fig.savefig(os.path.join(figures_dir, "anomaly_scatter.png"), dpi=150)
    plt.close(fig)


def generate_summary(reports_dir, db_path=None):
    if db_path is None:
        db_path = os.path.join(PROJECT_ROOT, "data", "sustainment.db")

    conn = sqlite3.connect(db_path)

    engine_count = conn.execute("SELECT COUNT(*) FROM engines").fetchone()[0]
    wo_count = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    replacement_count = conn.execute("SELECT COUNT(*) FROM part_replacements").fetchone()[0]

    availability_df = _load_csv(reports_dir, "fleet_availability_score")
    avg_availability = availability_df["availability_pct"].mean()

    top_parts = conn.execute("""
        SELECT p.part_name, ROUND(SUM(pr.quantity * p.unit_cost_usd), 0) AS total_cost
        FROM part_replacements pr
        JOIN parts p ON pr.part_id = p.part_id
        GROUP BY p.part_id
        ORDER BY total_cost DESC
        LIMIT 3
    """).fetchall()

    highest_unsched = conn.execute("""
        SELECT e.engine_model,
               ROUND(100.0 * SUM(CASE WHEN wo.event_type = 'Unscheduled' THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM work_orders wo
        JOIN engines e ON wo.engine_id = e.engine_id
        GROUP BY e.engine_model
        ORDER BY 2 DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    summary = f"""# Sustainment Analytics — Run Summary

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Record Counts

| Table | Count |
|---|---|
| Engines | {engine_count} |
| Work Orders | {wo_count} |
| Parts Replaced | {replacement_count} |

## Key Metrics

- **Fleet-wide Availability:** {avg_availability:.1f}%
- **Highest Unscheduled Rate:** {highest_unsched[0]} ({highest_unsched[1]}%)
- **Top 3 Costliest Parts:**
  1. {top_parts[0][0]} (${top_parts[0][1]:,.0f})
  2. {top_parts[1][0]} (${top_parts[1][1]:,.0f})
  3. {top_parts[2][0]} (${top_parts[2][1]:,.0f})

## Visualizations

![Failure Heatmap](figures/failure_heatmap.png)

![Monthly Cost Trend](figures/monthly_cost_trend.png)

![Fleet Availability](figures/fleet_availability.png)

![Anomaly Scatter](figures/anomaly_scatter.png)
"""

    with open(os.path.join(reports_dir, "summary.md"), "w") as f:
        f.write(summary)


def generate_all(reports_dir=None, db_path=None):
    if reports_dir is None:
        reports_dir = os.path.join(PROJECT_ROOT, "reports")

    figures_dir = os.path.join(reports_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    print("Generating failure heatmap...")
    plot_failure_heatmap(reports_dir, figures_dir)

    print("Generating monthly cost trend...")
    plot_monthly_cost_trend(reports_dir, figures_dir)

    print("Generating fleet availability chart...")
    plot_fleet_availability(reports_dir, figures_dir)

    print("Generating anomaly scatter plot...")
    plot_anomaly_scatter(reports_dir, figures_dir)

    print("Generating summary report...")
    generate_summary(reports_dir, db_path)

    print(f"Reports saved to {reports_dir}")


if __name__ == "__main__":
    generate_all()
