"""Data preprocessing: loading, cleaning, imputation for CRP dataset."""

import numpy as np
import pandas as pd


# Columns chứa thông tin post-trip (leakage)
LEAKAGE_COLS = ["est_time_arrival", "est_distance_arrival", "estimate_dropoff_time", "total_pay"]
# Columns ID không generalizable
ID_COLS = ["order_id", "matching_batch_id", "driver_id"]
TARGET = "is_completed"


def load_data(path: str, sep: str = "\t") -> pd.DataFrame:
    """Load dataset từ CSV hoặc Parquet."""
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
        if "Unnamed: 0" in df.columns:
            df = df.drop(columns=["Unnamed: 0"])
    else:
        df = pd.read_csv(path, sep=sep, index_col=0)
    print(f"Loaded: {df.shape[0]:,} rows × {df.shape[1]} columns")
    return df


def remove_leakage_features(df: pd.DataFrame) -> pd.DataFrame:
    """Loại bỏ features chỉ biết sau khi cuốc xe diễn ra."""
    existing = [c for c in LEAKAGE_COLS if c in df.columns]
    if existing:
        df = df.drop(columns=existing)
        print(f"Dropped leakage: {existing}")
    return df


def remove_id_columns(df: pd.DataFrame, keep_driver_id: bool = False) -> pd.DataFrame:
    """Loại bỏ ID columns (không dùng cho modeling).

    Args:
        keep_driver_id: Giữ driver_id cho aggregation features (dataset lớn)
    """
    cols_to_drop = [c for c in ID_COLS if c in df.columns]
    if keep_driver_id and "driver_id" in cols_to_drop:
        cols_to_drop.remove("driver_id")
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        print(f"Dropped IDs: {cols_to_drop}")
    if keep_driver_id and "driver_id" in df.columns:
        print(f"Kept driver_id for aggregation")
    return df


def remove_constant_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Loại bỏ columns chỉ có 1 giá trị (vd: travel_mode=2 constant)."""
    constant = [c for c in df.columns if df[c].nunique() <= 1 and c != TARGET]
    if constant:
        df = df.drop(columns=constant)
        print(f"Dropped constant: {constant}")
    return df


def impute_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Impute missing values.

    eta_std, eda_std: NaN khi chỉ có 1 driver candidate → fill 0 (no variance).
    """
    for col in ["eta_std", "eda_std"]:
        if col in df.columns:
            n_missing = df[col].isna().sum()
            if n_missing > 0:
                df[col] = df[col].fillna(0)
                print(f"Imputed {col}: {n_missing} NaN → 0")
    return df


def fix_negative_waiting_time(df: pd.DataFrame) -> pd.DataFrame:
    """Xử lý outlier: user_waiting_time_seconds âm → thay bằng median non-negative.

    Các giá trị âm (~-870 đến -898s) là data quality issue (clock skew hoặc
    pipeline error), không phải thời gian chờ thực tế. Thay bằng median thay
    vì clip về 0 để tránh tạo ra nhóm giả "chờ 0 giây".
    """
    col = "user_waiting_time_seconds"
    if col not in df.columns:
        return df

    mask_neg = df[col] < 0
    n_neg = mask_neg.sum()
    if n_neg > 0:
        median_val = df.loc[~mask_neg, col].median()
        df.loc[mask_neg, col] = median_val
        print(f"Imputed {col}: {n_neg} giá trị âm → median ({median_val:.1f}s)")
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Full preprocessing pipeline. Auto-detect dataset size for driver_id handling."""
    df = df.copy()
    df = remove_leakage_features(df)

    # Dataset lớn (>10K): giữ driver_id cho aggregation features
    keep_driver = len(df) > 10000 and "driver_id" in df.columns
    df = remove_id_columns(df, keep_driver_id=keep_driver)

    df = remove_constant_columns(df)
    df = impute_missing(df)
    df = fix_negative_waiting_time(df)
    return df


def get_X_y(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Tách features và target."""
    features = [c for c in df.columns if c != TARGET]
    return df[features], df[TARGET]
