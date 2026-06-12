"""
Stage 1: Ingest
Loads raw CSV sources, validates schemas, and performs basic type coercion.
"""
import pandas as pd
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Expected schema: {column: dtype}
SCHEMAS = {
    "freMTPL2freq": {
        "IDpol":       "int",    # policy ID
        "ClaimNb":     "int",    # number of claims
        "Exposure":    "float",  # fraction of year insured
        "Area":        "str",    # area code A–F
        "VehPower":    "int",    # vehicle power (horsepower band)
        "VehAge":      "int",    # vehicle age in years
        "DrivAge":     "int",    # driver age
        "BonusMalus":  "int",    # bonus-malus score (50=best, 230=worst)
        "VehBrand":    "str",    # anonymised brand code
        "VehGas":      "str",    # Regular / Diesel
        "Density":     "int",    # population density of municipality
        "Region":      "str",    # French region code
    },
    "drivers": {
        "driver_id": "str",
        "age": "int",
        "gender": "str",
        "years_licensed": "int",
        "postcode": "str",
        "licence_points": "int",
        "prior_claims_3yr": "int",
    },
    "vehicles": {
        "vehicle_id": "str",
        "driver_id": "str",
        "make": "str",
        "year": "int",
        "engine_cc": "int",
        "value_gbp": "float",
        "annual_mileage": "int",
        "usage_type": "str",
    },
    "telematics": {
        "driver_id": "str",
        "avg_speed_mph": "float",
        "harsh_braking_events_pm": "float",
        "harsh_accel_events_pm": "float",
        "night_driving_pct": "float",
        "motorway_pct": "float",
        "phone_use_events_pm": "float",
    },
    "claims": {
        "claim_id": "str",
        "driver_id": "str",
        "claim_date": "datetime",
        "claim_type": "str",
        "claim_amount_gbp": "float",
        "at_fault": "bool",
    },
}


def load_source(path: Path, name: str) -> pd.DataFrame:
    """Load a single CSV with schema validation."""
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    df = pd.read_csv(path)
    schema = SCHEMAS.get(name, {})
    missing = set(schema.keys()) - set(df.columns)
    if missing:
        raise ValueError(f"[{name}] Missing columns: {missing}")

    # Coerce types
    for col, dtype in schema.items():
        try:
            if dtype == "datetime":
                df[col] = pd.to_datetime(df[col])
            elif dtype == "bool":
                df[col] = df[col].astype(bool)
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logger.warning(f"[{name}] Could not coerce '{col}' to {dtype}: {e}")

    logger.info(f"[{name}] Loaded {len(df):,} rows, {len(df.columns)} cols")
    return df


def ingest(raw_dir: str) -> Dict[str, pd.DataFrame]:
    """Load all raw sources from directory."""
    raw_path = Path(raw_dir)
    sources = {}

    for name in SCHEMAS:
        file_path = raw_path / f"{name}.csv"
        try:
            sources[name] = load_source(file_path, name)
        except FileNotFoundError:
            logger.warning(f"[{name}] File not found — skipping.")
    return sources
