import sys
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocessing import load_data, preprocess
from src.features.transformations import (
    add_supply_demand_features,
    add_confidence_features,
    add_trip_value_features,
    add_binary_flags,
    add_date_features,
)

FEAST_DATA_DIR = Path(__file__).parent / "data"

# Columns for each feature view (must match definitions.py)
RAW_FEATURE_COLS = [
    "order_id", "event_timestamp",
    "num_drivers", "num_orders",
    "eta_avg", "eta_std", "eta_min",
    "eda_avg", "eda_std", "eda_min",
    "distance", "total_fee",
    "hour_of_day", "minute_of_hour", "rush_hour",
    "user_waiting_time_seconds",
]

DERIVED_FEATURE_COLS = [
    "order_id", "event_timestamp",
    "supply_demand_ratio", "demand_supply_ratio",
    "eta_confidence", "eda_confidence",
    "fee_per_km", "eta_per_km", "eta_eda_ratio", "pickup_to_trip_ratio",
    "is_short_trip", "is_long_eta", "is_high_wait", "is_negative_wait", "is_single_driver",
    "day_of_week", "is_weekend", "is_friday", "rush_hour_weekday",
]


def prepare_feast_data(
    data_path: str | None = None,
    sample_size: int = 50_000,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Load raw data, generate Feast-compatible parquet files.

    Returns: (raw_features_df, derived_features_df, labels)
    """
    if data_path is None:
        data_path = str(PROJECT_ROOT / "data" / "raw" / "Completion_prediction__dataset__hashing_500k.parquet")

    # Load & preprocess (keep driver_id handling as-is)
    df = load_data(data_path)

    # Sample for faster iteration
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=seed).reset_index(drop=True)
        print(f"Sampled to {sample_size:,} rows")

    # Save labels before preprocessing drops them
    labels = df["is_completed"].copy() if "is_completed" in df.columns else None

    # Keep order_id for entity key
    order_ids = df["order_id"].copy() if "order_id" in df.columns else pd.Series(range(len(df)), name="order_id")

    # Preprocess (removes leakage, IDs, constants, imputes)
    df_proc = preprocess(df)

    # Generate synthetic event timestamps (spread over 30 days)
    np.random.seed(seed)
    base_time = datetime(2025, 1, 1)
    random_offsets = np.random.uniform(0, 30 * 24 * 3600, size=len(df_proc))
    event_timestamps = pd.Series([
        base_time + timedelta(seconds=float(s)) for s in random_offsets
    ])

    # Add back order_id and timestamp
    df_proc["order_id"] = order_ids.values[:len(df_proc)]
    df_proc["event_timestamp"] = event_timestamps

    # ── Raw features parquet ──
    raw_cols = [c for c in RAW_FEATURE_COLS if c in df_proc.columns]
    raw_df = df_proc[raw_cols].copy()

    # ── Derived features: compute from preprocessed data ──
    df_derived = df_proc.copy()
    df_derived = add_supply_demand_features(df_derived)
    df_derived = add_confidence_features(df_derived)
    df_derived = add_trip_value_features(df_derived)
    df_derived = add_binary_flags(df_derived)

    # Date features (need 'date' column — synthesize from event_timestamp)
    df_derived["date"] = df_derived["event_timestamp"].dt.date
    df_derived["date"] = pd.to_datetime(df_derived["date"])
    df_derived["day_of_week"] = df_derived["date"].dt.dayofweek
    df_derived["is_weekend"] = (df_derived["day_of_week"] >= 5).astype(int)
    df_derived["is_friday"] = (df_derived["day_of_week"] == 4).astype(int)
    df_derived["rush_hour_weekday"] = df_derived["rush_hour"] * (1 - df_derived["is_weekend"])

    derived_cols = [c for c in DERIVED_FEATURE_COLS if c in df_derived.columns]
    derived_df = df_derived[derived_cols].copy()

    # ── Save parquet files ──
    FEAST_DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = FEAST_DATA_DIR / "raw_features.parquet"
    derived_path = FEAST_DATA_DIR / "derived_features.parquet"
    labels_path = FEAST_DATA_DIR / "labels.parquet"

    raw_df.to_parquet(raw_path, index=False)
    derived_df.to_parquet(derived_path, index=False)

    if labels is not None:
        labels_df = pd.DataFrame({
            "order_id": order_ids.values[:len(labels)],
            "event_timestamp": event_timestamps,
            "is_completed": labels.values[:len(df_proc)],
        })
        labels_df.to_parquet(labels_path, index=False)
    else:
        labels_df = None

    print(f"\nFeast data prepared:")
    print(f"  Raw features:     {raw_path} ({len(raw_df):,} rows, {len(raw_df.columns)} cols)")
    print(f"  Derived features: {derived_path} ({len(derived_df):,} rows, {len(derived_df.columns)} cols)")
    if labels_df is not None:
        print(f"  Labels:           {labels_path} ({len(labels_df):,} rows)")

    return raw_df, derived_df, labels


def load_parquet_to_redshift(
    region: str = "ap-southeast-1",
    workgroup: str = "crp-feast-wg",
    database: str = "dev",
    iam_role: str = "arn:aws:iam::516909141871:role/redshift-s3-feast-role",
) -> None:
    """
    Create Redshift tables and COPY from existing S3 parquet files.
    Assumes files already exist at s3://crp-feature-store-data/*.parquet.
    """
    import boto3
    import time as _time

    redshift = boto3.client("redshift-data", region_name=region)

    TABLES = {
        "order_raw_features":     "s3://crp-feature-store-data/feast/raw_features.parquet",
        "order_derived_features": "s3://crp-feature-store-data/feast/derived_features.parquet",
    }

    def _run_sql(sql: str, label: str) -> None:
        resp = redshift.execute_statement(
            WorkgroupName=workgroup,
            Database=database,
            Sql=sql,
        )
        stmt_id = resp["Id"]
        for _ in range(60):
            desc = redshift.describe_statement(Id=stmt_id)
            status = desc["Status"]
            if status == "FINISHED":
                return
            if status in ("FAILED", "ABORTED"):
                raise RuntimeError(f"Redshift SQL failed [{label}]: {desc.get('Error', 'unknown')}")
            _time.sleep(2)
        raise TimeoutError(f"Redshift statement timed out [{label}]")

    for table_name, s3_path in TABLES.items():
        print(f"  [{table_name}] Inferring schema from S3 parquet...")
        # Read schema from local parquet (already saved by prepare_feast_data)
        local_path = FEAST_DATA_DIR / f"{table_name.replace('order_', '')}.parquet"
        schema_df = pd.read_parquet(local_path, columns=None).head(0)

        def _dtype(dtype):
            if pd.api.types.is_integer_dtype(dtype): return "BIGINT"
            if pd.api.types.is_float_dtype(dtype):   return "FLOAT8"
            if pd.api.types.is_datetime64_any_dtype(dtype): return "TIMESTAMP"
            return "VARCHAR(256)"

        col_defs = ", ".join(f'"{c}" {_dtype(schema_df[c].dtype)}' for c in schema_df.columns)
        create_sql = f'DROP TABLE IF EXISTS "{table_name}"; CREATE TABLE "{table_name}" ({col_defs});'
        print(f"  [{table_name}] Creating table...")
        _run_sql(create_sql, f"create {table_name}")

        copy_sql = (
            f"COPY \"{table_name}\" FROM '{s3_path}' "
            f"IAM_ROLE '{iam_role}' FORMAT AS PARQUET;"
        )
        print(f"  [{table_name}] COPY from {s3_path}...")
        _run_sql(copy_sql, f"copy {table_name}")
        print(f"  [{table_name}] Done.")


if __name__ == "__main__":
    prepare_feast_data()
