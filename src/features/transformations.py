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


def add_date_features(df: pd.DataFrame) -> pd.DataFrame:
    """Date-based features (cần cột 'date')."""
    if "date" not in df.columns:
        return df

    import pandas as pd
    df["date"] = pd.to_datetime(df["date"])
    df["day_of_week"] = df["date"].dt.dayofweek  # 0=Mon, 6=Sun
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_friday"] = (df["day_of_week"] == 4).astype(int)

    # Rush hour chỉ có ý nghĩa ngày thường — cuối tuần rush/non-rush gần bằng nhau
    df["rush_hour_weekday"] = df["rush_hour"] * (1 - df["is_weekend"])

    # Drop cột date gốc (string/datetime, không dùng cho model)
    df = df.drop(columns=["date"])

    print(f"Created date features: day_of_week, is_weekend, is_friday, rush_hour_weekday")
    return df


def add_driver_aggregation(df: pd.DataFrame, min_records: int = 5, smoothing: int = 30) -> pd.DataFrame:
    """Driver-level aggregation features (cross-validated style within dataset).

    Tính mean completion rate per driver, smoothed với global mean.
    Chỉ áp dụng khi dataset đủ lớn (nhiều records per driver).
    Lưu ý: đây KHÔNG phải target encoding CV — chỉ là simple smoothed mean trên full data.
    Khi dùng trong CV pipeline, cần tính lại bên trong mỗi fold để tránh leakage.
    """
    if "driver_id" not in df.columns:
        return df

    global_mean = df["is_completed"].mean() if "is_completed" in df.columns else 0.5

    driver_stats = df.groupby("driver_id")["is_completed"].agg(["mean", "count"])
    driver_stats["smoothed_cr"] = (
        driver_stats["count"] * driver_stats["mean"] + smoothing * global_mean
    ) / (driver_stats["count"] + smoothing)

    df["driver_order_count"] = df["driver_id"].map(driver_stats["count"])
    df["driver_completion_rate_smoothed"] = df["driver_id"].map(driver_stats["smoothed_cr"])

    # Drop driver_id sau khi đã extract features
    df = df.drop(columns=["driver_id"])

    n_with_enough = (driver_stats["count"] >= min_records).sum()
    print(f"Created driver features: driver_order_count, driver_completion_rate_smoothed")
    print(f"  Drivers with >={min_records} records: {n_with_enough:,} ({n_with_enough/len(driver_stats):.1%})")
    return df


def build_features(df: pd.DataFrame, use_date: bool = True, use_driver_agg: bool = True) -> pd.DataFrame:
    """Run full feature engineering pipeline.

    Args:
        use_date: Tạo date features nếu cột 'date' tồn tại
        use_driver_agg: Tạo driver aggregation features nếu cột 'driver_id' tồn tại và data đủ lớn
    """
    df = df.copy()
    df = add_supply_demand_features(df)
    df = add_confidence_features(df)
    df = add_trip_value_features(df)
    df = add_binary_flags(df)
    df = add_interaction_features(df)
    df = add_time_features(df)

    if use_date:
        df = add_date_features(df)

    # KHÔNG tính driver aggregation ở đây — gây target leakage
    # Phải dùng cross-validated target encoding trong pipeline (improvements.py)
    if "driver_id" in df.columns:
        df = df.drop(columns=["driver_id"])
        print("Dropped driver_id (use CV target encoding in pipeline instead)")

    print(f"Total features: {len([c for c in df.columns if c != 'is_completed'])}")
    return df
