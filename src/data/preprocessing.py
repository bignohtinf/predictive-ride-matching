"""Data preprocessing: cleaning, imputation, outlier handling."""

import numpy as np
import pandas as pd
from loguru import logger


def clip_outliers(df: pd.DataFrame, columns: list[str], lower_pct: float = 1, upper_pct: float = 99) -> pd.DataFrame:
    """Clip outliers at specified percentiles."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            lower = np.percentile(df[col].dropna(), lower_pct)
            upper = np.percentile(df[col].dropna(), upper_pct)
            df[col] = df[col].clip(lower, upper)
            logger.info(f"Clipped {col}: [{lower:.2f}, {upper:.2f}]")
    return df


def impute_missing(df: pd.DataFrame, group_cols: list[str] = None) -> pd.DataFrame:
    """Impute missing values using median, optionally grouped."""
    df = df.copy()
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    if group_cols:
        for col in numeric_cols:
            if df[col].isna().any():
                df[col] = df.groupby(group_cols)[col].transform(lambda x: x.fillna(x.median()))
                # Fallback for groups that are entirely NaN
                df[col] = df[col].fillna(df[col].median())
    else:
        df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

    return df


def remove_leakage_features(df: pd.DataFrame) -> pd.DataFrame:
    """Remove features that leak future information."""
    leakage_cols = ["est_time_arrival", "est_distance_arrival", "estimate_dropoff_time", "total_pay"]
    existing = [c for c in leakage_cols if c in df.columns]
    if existing:
        logger.warning(f"Removing leakage features: {existing}")
        df = df.drop(columns=existing)
    return df


def temporal_train_test_split(
    df: pd.DataFrame,
    time_col: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data temporally (no random shuffle)."""
    df = df.sort_values(time_col).reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train = df.iloc[:train_end]
    val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:]

    logger.info(f"Split sizes - Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
    return train, val, test


def preprocess_pipeline(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Run full preprocessing pipeline."""
    logger.info(f"Starting preprocessing. Shape: {df.shape}")

    df = remove_leakage_features(df)

    outlier_features = config.get("outlier_features", [])
    pcts = config.get("outlier_clip_percentiles", [1, 99])
    df = clip_outliers(df, outlier_features, pcts[0], pcts[1])

    group_cols = ["travel_mode", "hour_of_day"] if "travel_mode" in df.columns else None
    df = impute_missing(df, group_cols=group_cols)

    logger.info(f"Preprocessing done. Shape: {df.shape}")
    return df
