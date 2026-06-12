"""
Stage 3: Risk Scoring
Computes a composite risk score per policy from driver, vehicle,
telematics, and claims features. Outputs risk band + estimated premium uplift.
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Weights for each risk dimension (must sum to 1.0)
WEIGHTS = {
    "driver_risk":     0.30,
    "vehicle_risk":    0.20,
    "telematics_risk": 0.25,
    "claims_risk":     0.25,
}

RISK_BANDS = [
    (0.00, 0.20, "Very Low",  0.80),
    (0.20, 0.35, "Low",       0.90),
    (0.35, 0.55, "Medium",    1.00),
    (0.55, 0.70, "High",      1.25),
    (0.70, 1.00, "Very High", 1.60),
]


def driver_risk_score(df: pd.DataFrame) -> pd.Series:
    """Normalised 0–1 driver risk from age, experience, points, prior claims."""
    age_risk = np.where(df["age"] < 25, 1.0,
               np.where(df["age"] > 70, 0.7,
               np.interp(df["age"], [25, 50, 70], [0.4, 0.2, 0.5])))

    exp_risk = (1 - (df["years_licensed"] / 50)).clip(0, 1)
    points_risk = (df["licence_points"] / 12).clip(0, 1)
    prior_risk = (df["prior_claims_3yr"] / 3).clip(0, 1)
    postcode_risk = ((df["postcode_risk_factor"] - 0.8) / 0.6).clip(0, 1)

    score = (
        0.25 * age_risk +
        0.20 * exp_risk +
        0.25 * points_risk +
        0.20 * prior_risk +
        0.10 * postcode_risk
    )
    return score.clip(0, 1).rename("driver_risk")


def vehicle_risk_score(df: pd.DataFrame) -> pd.Series:
    """Normalised 0–1 vehicle risk from age, value, mileage, make, usage."""
    age_risk = (df["vehicle_age_yr"] / 20).clip(0, 1)
    value_risk = (df["value_gbp"] / 45000).clip(0, 1)
    mileage_risk = (df["annual_mileage"] / 30000).clip(0, 1)
    make_risk = df["is_high_risk_make"].astype(float)
    usage_risk = ((df["usage_risk_factor"] - 1.0) / 0.35).clip(0, 1)
    engine_risk = ((df["engine_cc"] - 1000) / 2000).clip(0, 1)

    score = (
        0.20 * age_risk +
        0.20 * value_risk +
        0.20 * mileage_risk +
        0.15 * make_risk +
        0.15 * usage_risk +
        0.10 * engine_risk
    )
    return score.clip(0, 1).rename("vehicle_risk")


def claims_risk_score(df: pd.DataFrame) -> pd.Series:
    """Normalised 0–1 claims risk from frequency, fault, severity."""
    freq_risk = (df["total_claims"] / 5).clip(0, 1)
    fault_risk = (df["at_fault_claims"] / df["total_claims"].replace(0, 1)).clip(0, 1)
    severity_risk = (df["avg_claim_value"] / 10000).clip(0, 1)

    score = (
        0.40 * freq_risk +
        0.35 * fault_risk +
        0.25 * severity_risk
    )
    return score.clip(0, 1).rename("claims_risk")


def assign_risk_band(score: float):
    for low, high, band, multiplier in RISK_BANDS:
        if low <= score < high:
            return band, multiplier
    return "Very High", 1.60


BASE_PREMIUM_GBP = 600  # UK average base premium


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Add risk scores, band, and estimated premium to the DataFrame."""
    df = df.copy()

    df["driver_risk"]     = driver_risk_score(df)
    df["vehicle_risk"]    = vehicle_risk_score(df)
    df["telematics_risk"] = df.get("telematics_score", pd.Series(0.5, index=df.index))
    df["claims_risk"]     = claims_risk_score(df)

    # Composite weighted score
    df["composite_risk_score"] = sum(
        WEIGHTS[dim] * df[dim] for dim in WEIGHTS
    ).round(4)

    # Band and premium
    band_data = df["composite_risk_score"].apply(assign_risk_band)
    df["risk_band"]            = band_data.apply(lambda x: x[0])
    df["premium_multiplier"]   = band_data.apply(lambda x: x[1])
    df["estimated_premium_gbp"] = (BASE_PREMIUM_GBP * df["premium_multiplier"]).round(2)

    logger.info(
        f"[scoring] Risk bands:\n"
        + df["risk_band"].value_counts().to_string()
    )
    return df
