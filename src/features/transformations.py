"""Feature engineering: Tier 1 derived features từ data hiện có."""

import numpy as np
import pandas as pd


def add_supply_demand_features(df: pd.DataFrame) -> pd.DataFrame:
    """Supply-demand dynamics."""
    df["supply_demand_ratio"] = df["num_drivers"] / (df["num_orders"] + 1)
    df["demand_supply_ratio"] = df["num_orders"] / (df["num_drivers"] + 1)
    return df


def add_confidence_features(df: pd.DataFrame) -> pd.DataFrame:
    """Routing uncertainty (coefficient of variation)."""
    df["eta_confidence"] = df["eta_std"] / (df["eta_avg"] + 1)
    df["eda_confidence"] = df["eda_std"] / (df["eda_avg"] + 0.01)
    return df


def add_trip_value_features(df: pd.DataFrame) -> pd.DataFrame:
    """Trip value và pricing signals."""
    df["fee_per_km"] = df["total_fee"] / (df["distance"] + 0.01)
    df["eta_per_km"] = df["eta_avg"] / (df["eda_avg"] + 0.01)
    df["eta_eda_ratio"] = df["eta_avg"] / (df["eda_avg"] + 0.01)
    df["pickup_to_trip_ratio"] = df["eda_avg"] / (df["distance"] + 0.01)
    return df


def add_binary_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Binary flags cho các điều kiện đặc biệt."""
    df["is_short_trip"] = (df["distance"] < 2).astype(int)
    df["is_long_eta"] = (df["eta_avg"] > 900).astype(int)
    df["is_high_wait"] = (df["user_waiting_time_seconds"] > 120).astype(int)
    df["is_negative_wait"] = (df["user_waiting_time_seconds"] < 0).astype(int)
    df["is_single_driver"] = (df["num_drivers"] == 1).astype(int)
    return df


def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature interactions có ý nghĩa domain."""
    df["short_trip_rush"] = df["is_short_trip"] * df["rush_hour"]
    df["low_supply_flag"] = (df["supply_demand_ratio"] < 0.2).astype(int)
    df["low_supply_short_trip"] = df["low_supply_flag"] * df["is_short_trip"]
    df["high_eta_rush"] = df["is_long_eta"] * df["rush_hour"]
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Temporal features."""
    df["minutes_since_midnight"] = df["hour_of_day"] * 60 + df["minute_of_hour"]
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_of_day"] / 24)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Run full Tier 1 feature engineering pipeline."""
    df = df.copy()
    df = add_supply_demand_features(df)
    df = add_confidence_features(df)
    df = add_trip_value_features(df)
    df = add_binary_flags(df)
    df = add_interaction_features(df)
    df = add_time_features(df)

    new_cols = [
        "supply_demand_ratio", "demand_supply_ratio",
        "eta_confidence", "eda_confidence",
        "fee_per_km", "eta_per_km", "eta_eda_ratio", "pickup_to_trip_ratio",
        "is_short_trip", "is_long_eta", "is_high_wait", "is_negative_wait", "is_single_driver",
        "short_trip_rush", "low_supply_flag", "low_supply_short_trip", "high_eta_rush",
        "minutes_since_midnight", "hour_sin", "hour_cos",
    ]
    print(f"Created {len(new_cols)} derived features")
    return df
