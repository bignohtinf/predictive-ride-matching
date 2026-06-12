import subprocess
import sys
import time
from pathlib import Path
from src.features.feature_store.prepare_feast_data import prepare_feast_data, load_parquet_to_redshift


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FEAST_REPO = Path(__file__).parent


def step_prepare_data(sample_size: int = 50_000):
    """Step 1: Ingest raw data → parquet."""
    print("\n" + "=" * 60)
    print("STEP 1: Prepare Feast Data")
    print("=" * 60)
    raw_df, derived_df, labels = prepare_feast_data(sample_size=sample_size)
    return raw_df, derived_df, labels


def step_load_to_redshift():
    """Step 1b: Create Redshift tables and COPY from existing S3 parquet files."""
    print("\n" + "=" * 60)
    print("STEP 1b: Load S3 Parquet → Redshift")
    print("=" * 60)
    load_parquet_to_redshift()
    print("  Load complete.")


def step_feast_apply():
    """Step 2: Register feature definitions with Feast."""
    print("\n" + "=" * 60)
    print("STEP 2: feast apply (Register Feature Definitions)")
    print("=" * 60)
    result = subprocess.run(
        ["feast", "apply"],
        cwd=str(FEAST_REPO),
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return False
    print("Feature definitions registered successfully.")
    return True


def step_retrieve_historical():
    """Step 3: Retrieve historical features (offline serving via point-in-time join)."""
    print("\n" + "=" * 60)
    print("STEP 3: Retrieve Historical Features (Offline Serving)")
    print("=" * 60)
    from feast import FeatureStore
    import pandas as pd

    store = FeatureStore(repo_path=str(FEAST_REPO))

    labels_path = FEAST_REPO / "data" / "labels.parquet"
    entity_df = pd.read_parquet(labels_path)
    entity_df["order_id"] = entity_df["order_id"].astype(str)

    feature_refs = [
        "order_raw_features:num_drivers",
        "order_raw_features:num_orders",
        "order_raw_features:eta_avg",
        "order_raw_features:eta_std",
        "order_raw_features:distance",
        "order_raw_features:total_fee",
        "order_raw_features:user_waiting_time_seconds",
        "order_raw_features:hour_of_day",
        "order_raw_features:rush_hour",
        "order_derived_features:supply_demand_ratio",
        "order_derived_features:fee_per_km",
        "order_derived_features:is_short_trip",
        "order_derived_features:is_long_eta",
        "order_derived_features:day_of_week",
        "order_derived_features:is_weekend",
        "on_demand_interactions:hour_sin",
        "on_demand_interactions:hour_cos",
        "on_demand_interactions:short_trip_rush",
        "on_demand_interactions:low_supply_flag",
    ]

    t0 = time.time()
    training_df = store.get_historical_features(
        entity_df=entity_df[["order_id", "event_timestamp"]],
        features=feature_refs,
    ).to_df()
    elapsed = time.time() - t0

    print(f"  Retrieved: {training_df.shape[0]:,} rows × {training_df.shape[1]} cols")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Sample:\n{training_df.head(3).to_string()}")
    return training_df


def step_materialize_online():
    """Step 4 (Optional): Materialize to Redis online store."""
    print("\n" + "=" * 60)
    print("STEP 4: Materialize to Online Store (Redis)")
    print("=" * 60)
    try:
        from src.features.feature_store.online_store_mock import materialize_to_online_store
        materialize_to_online_store()
        return True
    except Exception as e:
        print(f"  Redis not available: {e}")
        print("  Running demo mode instead...")
        from src.features.feature_store.online_store_mock import demo_online_serving
        demo_online_serving()
        return False


def step_compare():
    """Step 5: Run baseline vs Feast performance comparison."""
    print("\n" + "=" * 60)
    print("STEP 5: Performance Comparison (Baseline vs Feast)")
    print("=" * 60)
    from pipelines.training.feast_pipeline import run_comparison
    return run_comparison()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Feast Feature Store orchestration")
    parser.add_argument("--sample-size", type=int, default=50_000)
    parser.add_argument("--online", action="store_true", help="Include Redis materialization")
    parser.add_argument("--compare", action="store_true", help="Run baseline vs Feast comparison")
    parser.add_argument("--skip-prepare", action="store_true", help="Skip data preparation")
    args = parser.parse_args()

    t_start = time.time()

    # Step 1: Prepare data
    if not args.skip_prepare:
        step_prepare_data(args.sample_size)
    step_load_to_redshift()

    # Step 2: Register with Feast
    if not step_feast_apply():
        print("feast apply failed. Aborting.")
        sys.exit(1)

    # Step 3: Retrieve historical features
    training_df = step_retrieve_historical()

    # Step 4: Optional online store
    if args.online:
        step_materialize_online()

    # Step 5: Optional comparison
    if args.compare:
        step_compare()

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"DONE in {elapsed:.0f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
