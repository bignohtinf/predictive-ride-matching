"""Feature transformations: derived features, cyclical encoding, etc."""

import numpy as np
import pandas as pd


def add_supply_demand_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add supply-demand ratio features."""
    df = df.copy()
    df["supply_demand_ratio"] = df["num_drivers"] / (df["num_orders"] + 1)
    df["batch_competition"] = df["num_orders"] / (df["num_drivers"] + 1)
    return df


def add_cyclical_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode hour_of_day as sin/cos for cyclical continuity."""
    df = df.copy()
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_of_day"] / 24)
    return df


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add all derived features from existing columns."""
    df = df.copy()

    # ETA to distance ratio (proxy for expected speed)
    df["eta_to_distance_ratio"] = df["eta_avg"] / (df["eda_avg"] + 0.01)

    # Price per km
    df["fee_per_km"] = df["total_fee"] / (df["distance"] + 0.01)

    # Weekend flag (requires day_of_week)
    if "day_of_week" in df.columns:
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Waiting time buckets
    df["high_wait_flag"] = (df["user_waiting_time_seconds"] > 300).astype(int)

    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Run full feature engineering pipeline."""
    df = add_supply_demand_features(df)
    df = add_cyclical_time_features(df)
    df = add_derived_features(df)
    return df
