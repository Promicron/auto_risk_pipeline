"""Generate synthetic auto insurance raw data for pipeline testing."""
import pandas as pd
import numpy as np
import os

np.random.seed(42)
N = 500

def generate_drivers():
    ages = np.random.randint(18, 75, N)
    years_licensed = np.clip(ages - 17 - np.random.randint(0, 5, N), 0, 50)
    return pd.DataFrame({
        "driver_id": [f"DRV{i:04d}" for i in range(N)],
        "age": ages,
        "gender": np.random.choice(["M", "F", "Other"], N, p=[0.49, 0.49, 0.02]),
        "years_licensed": years_licensed,
        "postcode": np.random.choice(["B1", "B2", "CV1", "CV2", "WV1", "DY1"], N),
        "licence_points": np.random.choice([0, 0, 0, 3, 3, 6, 9], N),
        "prior_claims_3yr": np.random.choice([0, 0, 0, 1, 1, 2, 3], N),
    })

def generate_vehicles():
    makes = ["Ford", "Vauxhall", "BMW", "Audi", "Toyota", "Honda", "VW", "Mercedes"]
    return pd.DataFrame({
        "vehicle_id": [f"VEH{i:04d}" for i in range(N)],
        "driver_id": [f"DRV{i:04d}" for i in range(N)],
        "make": np.random.choice(makes, N),
        "year": np.random.randint(2005, 2024, N),
        "engine_cc": np.random.choice([1000, 1200, 1400, 1600, 2000, 2500, 3000], N),
        "value_gbp": np.random.randint(2000, 45000, N),
        "annual_mileage": np.random.randint(3000, 30000, N),
        "usage_type": np.random.choice(["Social", "Commute", "Business"], N, p=[0.4, 0.4, 0.2]),
    })

def generate_telematics():
    return pd.DataFrame({
        "driver_id": [f"DRV{i:04d}" for i in range(N)],
        "avg_speed_mph": np.random.normal(35, 10, N).clip(10, 80),
        "harsh_braking_events_pm": np.random.exponential(2, N).clip(0, 20),
        "harsh_accel_events_pm": np.random.exponential(1.5, N).clip(0, 15),
        "night_driving_pct": np.random.beta(2, 8, N),
        "motorway_pct": np.random.beta(3, 7, N),
        "phone_use_events_pm": np.random.exponential(0.5, N).clip(0, 10),
    })

def generate_claims():
    n_claims = 180
    return pd.DataFrame({
        "claim_id": [f"CLM{i:04d}" for i in range(n_claims)],
        "driver_id": [f"DRV{np.random.randint(0, N):04d}" for _ in range(n_claims)],
        "claim_date": pd.date_range("2022-01-01", periods=n_claims, freq="2D"),
        "claim_type": np.random.choice(["Collision", "Theft", "Weather", "Fire", "Liability"], n_claims),
        "claim_amount_gbp": np.random.exponential(3000, n_claims).clip(200, 50000).round(2),
        "at_fault": np.random.choice([True, False], n_claims, p=[0.45, 0.55]),
    })

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "raw")
    generate_drivers().to_csv(f"{out}/drivers.csv", index=False)
    generate_vehicles().to_csv(f"{out}/vehicles.csv", index=False)
    generate_telematics().to_csv(f"{out}/telematics.csv", index=False)
    generate_claims().to_csv(f"{out}/claims.csv", index=False)
    print("✓ Sample data written to data/raw/")
