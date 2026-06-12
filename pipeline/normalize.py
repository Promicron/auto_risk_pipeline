"""
Stage 2: Normalize
Cleans nulls, deduplicates, standardises categoricals, and joins all sources
into a single flat policy-level DataFrame.
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict

logger = logging.getLogger(__name__)

POSTCODE_RISK = {
    "B1": 1.3, "B2": 1.2, "CV1": 1.0, "CV2": 0.95,
    "WV1": 1.15, "DY1": 1.1,
}
USAGE_RISK = {"Social": 1.0, "Commute": 1.15, "Business": 1.35}
HIGH_RISK_MAKES = {"BMW", "Mercedes", "Audi"}


def clean_drivers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["driver_id"])
    df["age"] = df["age"].clip(17, 100)
    df["years_licensed"] = df["years_licensed"].clip(0, 60)
    df["licence_points"] = df["licence_points"].fillna(0).clip(0, 12)
    df["prior_claims_3yr"] = df["prior_claims_3yr"].fillna(0).clip(0, 10)
    df["gender"] = df["gender"].str.strip().str.title().fillna("Unknown")
    df["postcode_risk_factor"] = df["postcode"].map(POSTCODE_RISK).fillna(1.0)
    logger.info(f"[drivers] Cleaned → {len(df):,} rows")
    return df


def clean_vehicles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["vehicle_id"])
    df["vehicle_age_yr"] = 2025 - df["year"].clip(1990, 2025)
    df["is_high_risk_make"] = df["make"].isin(HIGH_RISK_MAKES).astype(int)
    df["usage_risk_factor"] = df["usage_type"].map(USAGE_RISK).fillna(1.0)
    df["value_gbp"] = df["value_gbp"].clip(500, 200000)
    df["annual_mileage"] = df["annual_mileage"].clip(1000, 100000)
    logger.info(f"[vehicles] Cleaned → {len(df):,} rows")
    return df


def clean_telematics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["driver_id"])
    numeric_cols = [c for c in df.columns if c != "driver_id"]
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].median())
    # Composite telematics risk score (0–1)
    df["telematics_score"] = (
        0.25 * (df["harsh_braking_events_pm"] / df["harsh_braking_events_pm"].max()) +
        0.20 * (df["harsh_accel_events_pm"] / df["harsh_accel_events_pm"].max()) +
        0.20 * (df["phone_use_events_pm"] / df["phone_use_events_pm"].max()) +
        0.20 * df["night_driving_pct"] +
        0.15 * (df["avg_speed_mph"] / 80)
    ).clip(0, 1)
    logger.info(f"[telematics] Cleaned → {len(df):,} rows")
    return df


def aggregate_claims(df: pd.DataFrame) -> pd.DataFrame:
    """Roll claims up to driver level."""
    agg = df.groupby("driver_id").agg(
        total_claims=("claim_id", "count"),
        at_fault_claims=("at_fault", "sum"),
        total_claim_value=("claim_amount_gbp", "sum"),
        avg_claim_value=("claim_amount_gbp", "mean"),
        last_claim_date=("claim_date", "max"),
    ).reset_index()
    logger.info(f"[claims] Aggregated → {len(agg):,} driver records")
    return agg


def normalize(sources: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge all cleaned sources into a single policy-level DataFrame."""
    drivers = clean_drivers(sources["drivers"])
    vehicles = clean_vehicles(sources["vehicles"])
    telematics = clean_telematics(sources["telematics"])
    claims_agg = aggregate_claims(sources.get("claims", pd.DataFrame()))

    # Join on driver_id
    df = drivers.merge(vehicles, on="driver_id", how="left")
    df = df.merge(telematics, on="driver_id", how="left")
    df = df.merge(claims_agg, on="driver_id", how="left")

    # Fill missing claim stats with 0
    for col in ["total_claims", "at_fault_claims", "total_claim_value", "avg_claim_value"]:
        df[col] = df[col].fillna(0)

    logger.info(f"[normalize] Final merged dataset: {len(df):,} rows, {len(df.columns)} cols")
    return df
