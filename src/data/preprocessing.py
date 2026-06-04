"""Data preprocessing: loading, cleaning, imputation for CRP dataset."""

import numpy as np
import pandas as pd


# Columns chứa thông tin post-trip (leakage)
LEAKAGE_COLS = ["est_time_arrival", "est_distance_arrival", "estimate_dropoff_time", "total_pay"]
# Columns ID không generalizable
ID_COLS = ["order_id", "matching_batch_id", "driver_id"]
TARGET = "is_completed"


def load_data(path: str, sep: str = "\t") -> pd.DataFrame:
    """Load dataset từ CSV (tab-separated mặc định cho data thật)."""
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


def remove_id_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Loại bỏ ID columns (không dùng cho modeling)."""
    existing = [c for c in ID_COLS if c in df.columns]
    if existing:
        df = df.drop(columns=existing)
        print(f"Dropped IDs: {existing}")
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


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Full preprocessing pipeline."""
    df = df.copy()
    df = remove_leakage_features(df)
    df = remove_id_columns(df)
    df = remove_constant_columns(df)
    df = impute_missing(df)
    return df


def get_X_y(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Tách features và target."""
    features = [c for c in df.columns if c != TARGET]
    return df[features], df[TARGET]
