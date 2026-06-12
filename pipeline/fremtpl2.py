"""
freMTPL2freq adapter
====================
Normalize and risk-score the French Motor Third-Party Liability dataset.

Column reference:
  IDpol      – policy ID
  ClaimNb    – number of claims during the exposure period
  Exposure   – fraction of the year the policy was active (0–1)
  Area       – urbanisation code A (rural) → F (very urban)
  VehPower   – vehicle power band (integer, higher = more powerful)
  VehAge     – vehicle age in years
  DrivAge    – driver age in years
  BonusMalus – French bonus-malus coefficient (50 = best, up to 230)
  VehBrand   – anonymised brand (B1–B14)
  VehGas     – Regular / Diesel
  Density    – population density of the driver's municipality
  Region     – French administrative region code
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Area risk factor: A = rural/low-risk, F = dense urban/high-risk
AREA_RISK = {"A": 0.80, "B": 0.90, "C": 1.00, "D": 1.10, "E": 1.20, "F": 1.35}

# Approximate region risk factors based on French actuarial literature
REGION_RISK = {
    "R11": 1.20, "R24": 0.90, "R25": 0.95, "R31": 1.05, "R52": 1.00,
    "R53": 0.95, "R54": 1.00, "R72": 0.90, "R74": 0.85, "R82": 1.00,
    "R83": 1.10, "R91": 1.15, "R93": 1.10, "R94": 1.05,
    "R21": 0.90, "R22": 0.95, "R23": 0.90, "R26": 0.95, "R41": 0.95,
    "R42": 0.90, "R43": 0.90, "R51": 1.00, "R55": 0.95, "R73": 0.85,
    "R84": 1.05,
}

def normalize_fremtpl2(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and enrich freMTPL2freq for risk scoring."""
    df = df.copy()
    df = df.drop_duplicates(subset=["IDpol"])

    # Clip out-of-range values
    df["Exposure"]   = df["Exposure"].clip(0.01, 1.0)
    df["BonusMalus"] = df["BonusMalus"].clip(50, 230)
    df["DrivAge"]    = df["DrivAge"].clip(18, 100)
    df["VehAge"]     = df["VehAge"].clip(0, 40)
    df["VehPower"]   = df["VehPower"].clip(4, 15)
    df["Density"]    = df["Density"].clip(1, 30000)

    # Derived features
    df["area_risk_factor"]   = df["Area"].map(AREA_RISK).fillna(1.0)
    df["region_risk_factor"] = df["Region"].map(REGION_RISK).fillna(1.0)
    df["is_diesel"]          = (df["VehGas"] == "Diesel").astype(int)

    # Annualised claim frequency (claims per year of exposure)
    df["claim_frequency"] = (df["ClaimNb"] / df["Exposure"]).clip(0, 20)

    logger.info(f"[freMTPL2] Normalized → {len(df):,} rows")
    return df


def score_fremtpl2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute a composite risk score (0–1) and assign a risk band + premium multiplier.

    Dimensions:
      driver_risk    – age curve + BonusMalus (primary actuarial signal)
      vehicle_risk   – power, age, fuel type
      location_risk  – area urbanisation + region + density
      history_risk   – annualised claim frequency
    """
    df = df.copy()

    #  Driver risk 
    age = df["DrivAge"]
    age_curve = np.where(age < 25, 1.0,
                np.where(age > 70, 0.65,
                np.interp(age.clip(25, 70), [25, 40, 60, 70], [0.5, 0.25, 0.30, 0.55])))

    bm_norm = ((df["BonusMalus"] - 50) / 180).clip(0, 1)  # 50=0, 230=1

    df["driver_risk"] = (0.45 * bm_norm + 0.55 * age_curve).clip(0, 1)

    #  Vehicle risk 
    power_norm = ((df["VehPower"] - 4) / 11).clip(0, 1)
    age_norm   = (df["VehAge"] / 20).clip(0, 1)           # older = more risk
    diesel_adj = df["is_diesel"] * 0.05                   # slight diesel uplift

    df["vehicle_risk"] = (0.50 * power_norm + 0.35 * age_norm + 0.15 * diesel_adj).clip(0, 1)

    #  Location risk 
    area_norm    = ((df["area_risk_factor"] - 0.8) / 0.55).clip(0, 1)
    region_norm  = ((df["region_risk_factor"] - 0.85) / 0.35).clip(0, 1)
    density_norm = (np.log1p(df["Density"]) / np.log1p(30000)).clip(0, 1)

    df["location_risk"] = (0.35 * area_norm + 0.30 * region_norm + 0.35 * density_norm).clip(0, 1)

    #  Claims history risk 
    df["history_risk"] = (df["claim_frequency"] / 5).clip(0, 1)

    #  Composite 
    df["composite_risk_score"] = (
        0.35 * df["driver_risk"] +
        0.20 * df["vehicle_risk"] +
        0.25 * df["location_risk"] +
        0.20 * df["history_risk"]
    ).round(4)

    #  Band & premium 
    BANDS = [
        (0.00, 0.20, "Very Low",  0.75),
        (0.20, 0.35, "Low",       0.90),
        (0.35, 0.50, "Medium",    1.00),
        (0.50, 0.65, "High",      1.30),
        (0.65, 1.01, "Very High", 1.70),
    ]
    BASE_PREMIUM = 650  # EUR base

    def assign(score):
        for lo, hi, band, mult in BANDS:
            if lo <= score < hi:
                return band, mult
        return "Very High", 1.70

    band_data = df["composite_risk_score"].apply(assign)
    df["risk_band"]             = band_data.apply(lambda x: x[0])
    df["premium_multiplier"]    = band_data.apply(lambda x: x[1])
    df["estimated_premium_eur"] = (BASE_PREMIUM * df["premium_multiplier"]).round(2)

    logger.info(
        f"[freMTPL2] Risk bands:\n" + df["risk_band"].value_counts().to_string()
    )
    return df


def report_fremtpl2(df: pd.DataFrame, output_dir: str) -> dict:
    """Write scored data to SQLite and return a summary dict."""
    import sqlite3, json
    from pathlib import Path
    from datetime import datetime

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    db_path = f"{output_dir}/fremtpl2_risk.db"

    out_cols = [
        "IDpol", "ClaimNb", "Exposure", "Area", "VehPower", "VehAge",
        "DrivAge", "BonusMalus", "VehBrand", "VehGas", "Density", "Region",
        "claim_frequency", "driver_risk", "vehicle_risk", "location_risk",
        "history_risk", "composite_risk_score", "risk_band",
        "premium_multiplier", "estimated_premium_eur",
    ]
    cols = [c for c in out_cols if c in df.columns]
    with sqlite3.connect(db_path) as conn:
        df[cols].to_sql("policy_risk", conn, if_exists="replace", index=False)
    logger.info(f"[report] Wrote {len(df):,} rows → {db_path}")

    summary = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "dataset": "freMTPL2freq",
        "total_policies": len(df),
        "total_claims": int(df["ClaimNb"].sum()),
        "avg_claim_frequency": round(df["claim_frequency"].mean(), 4),
        "avg_composite_risk_score": round(df["composite_risk_score"].mean(), 4),
        "avg_estimated_premium_eur": round(df["estimated_premium_eur"].mean(), 2),
        "risk_band_distribution": df["risk_band"].value_counts().to_dict(),
        "risk_by_area": df.groupby("Area")["composite_risk_score"].mean().round(4).to_dict(),
        "risk_by_fuel": df.groupby("VehGas")["composite_risk_score"].mean().round(4).to_dict(),
        "top_risk_regions": df.groupby("Region")["composite_risk_score"]
            .mean().nlargest(5).round(4).to_dict(),
    }

    report_path = f"{output_dir}/fremtpl2_summary.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Print to console
    print("\n" + "=" * 62)
    print("  freMTPL2freq RISK PIPELINE — PORTFOLIO SUMMARY")
    print("=" * 62)
    print(f"  Run:               {summary['run_timestamp']}")
    print(f"  Policies:          {summary['total_policies']:,}")
    print(f"  Total Claims:      {summary['total_claims']:,}")
    print(f"  Avg Claim Freq:    {summary['avg_claim_frequency']}")
    print(f"  Avg Risk Score:    {summary['avg_composite_risk_score']}")
    print(f"  Avg Premium:       €{summary['avg_estimated_premium_eur']:,.2f}")
    print("\n  Risk Band Distribution:")
    order = ["Very Low", "Low", "Medium", "High", "Very High"]
    for band in order:
        count = summary["risk_band_distribution"].get(band, 0)
        bar = "█" * (count // 5000)
        print(f"    {band:<12} {count:>7,}  {bar}")
    print("\n  Avg Risk by Area (A=rural → F=urban):")
    for area in sorted(summary["risk_by_area"]):
        print(f"    Area {area}  {summary['risk_by_area'][area]}")
    print("\n  Top 5 Riskiest Regions:")
    for reg, score in summary["top_risk_regions"].items():
        print(f"    {reg}  {score}")
    print("=" * 62 + "\n")
    return summary
