"""
Stage 4: Report
Writes scored data to SQLite (swappable for PostgreSQL via SQLAlchemy),
and outputs a human-readable summary report.
"""
import pandas as pd
import sqlite3
import logging
import json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

OUTPUT_COLS = [
    "driver_id", "vehicle_id", "age", "gender", "postcode",
    "years_licensed", "licence_points", "prior_claims_3yr",
    "make", "year", "engine_cc", "value_gbp", "annual_mileage", "usage_type",
    "telematics_score",
    "total_claims", "at_fault_claims", "total_claim_value",
    "driver_risk", "vehicle_risk", "telematics_risk", "claims_risk",
    "composite_risk_score", "risk_band", "premium_multiplier", "estimated_premium_gbp",
]


def to_sqlite(df: pd.DataFrame, db_path: str, table: str = "policy_risk") -> None:
    """Upsert scored records into SQLite. Replace with SQLAlchemy for Postgres."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in OUTPUT_COLS if c in df.columns]
    with sqlite3.connect(db_path) as conn:
        df[cols].to_sql(table, conn, if_exists="replace", index=False)
    logger.info(f"[report] Wrote {len(df):,} rows to {db_path}::{table}")


def build_summary(df: pd.DataFrame) -> dict:
    """Compute portfolio-level risk metrics."""
    return {
        "run_timestamp": datetime.utcnow().isoformat(),
        "total_policies": len(df),
        "risk_band_distribution": df["risk_band"].value_counts().to_dict(),
        "avg_composite_risk_score": round(df["composite_risk_score"].mean(), 4),
        "avg_estimated_premium_gbp": round(df["estimated_premium_gbp"].mean(), 2),
        "total_claims_in_portfolio": int(df["total_claims"].sum()),
        "total_claim_value_gbp": round(df["total_claim_value"].sum(), 2),
        "pct_at_fault": round(
            df["at_fault_claims"].sum() / df["total_claims"].replace(0, 1).sum() * 100, 1
        ),
        "top_5_highest_risk": df.nlargest(5, "composite_risk_score")[
            ["driver_id", "composite_risk_score", "risk_band", "estimated_premium_gbp"]
        ].to_dict(orient="records"),
        "risk_by_usage_type": df.groupby("usage_type")["composite_risk_score"]
            .mean().round(4).to_dict(),
        "risk_by_postcode": df.groupby("postcode")["composite_risk_score"]
            .mean().round(4).to_dict(),
    }


def save_report(summary: dict, report_path: str) -> None:
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"[report] Summary written to {report_path}")


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("  AUTO INSURANCE RISK PIPELINE — PORTFOLIO SUMMARY")
    print("=" * 60)
    print(f"  Run:              {summary['run_timestamp']}")
    print(f"  Policies:         {summary['total_policies']:,}")
    print(f"  Avg Risk Score:   {summary['avg_composite_risk_score']}")
    print(f"  Avg Premium:      £{summary['avg_estimated_premium_gbp']:,.2f}")
    print(f"  Total Claims:     {summary['total_claims_in_portfolio']:,}  "
          f"(£{summary['total_claim_value_gbp']:,.0f})")
    print(f"  At-Fault %:       {summary['pct_at_fault']}%")
    print("\n  Risk Band Distribution:")
    for band, count in sorted(summary["risk_band_distribution"].items()):
        bar = "█" * (count // 5)
        print(f"    {band:<12} {count:>4}  {bar}")
    print("\n  Avg Risk by Usage:")
    for usage, score in summary["risk_by_usage_type"].items():
        print(f"    {usage:<12} {score}")
    print("=" * 60 + "\n")


def report(df: pd.DataFrame, output_dir: str) -> dict:
    db_path = f"{output_dir}/risk_pipeline.db"
    report_path = f"{output_dir}/summary.json"
    to_sqlite(df, db_path)
    summary = build_summary(df)
    save_report(summary, report_path)
    print_summary(summary)
    return summary
