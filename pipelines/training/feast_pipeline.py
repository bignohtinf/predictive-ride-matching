import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from src.data.preprocessing import load_data, preprocess, get_X_y
from src.features.transformations import build_features
from src.models.lightgbm_model import create_model as create_lgb
from src.models.xgboost_model import create_model as create_xgb
from src.evaluation.metrics import evaluate_oof, compare_models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import warnings
warnings.filterwarnings("ignore")

SEED = 42
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
N_EST = 500
FEAST_REPO = PROJECT_ROOT / "src" / "features" / "feature_store"


def run_baseline(data_path: str, sep: str = "\t") -> tuple[dict, pd.DataFrame, pd.Series, float]:
    """Run baseline pipeline (direct pandas transformations)."""
    t0 = time.time()
    df = load_data(data_path, sep=sep)
    df = preprocess(df)
    df = build_features(df)
    X, y = get_X_y(df)
    prep_time = time.time() - t0

    results = {}
    for name, model in [("LightGBM", create_lgb(N_EST)), ("XGBoost", create_xgb(N_EST))]:
        print(f"  Baseline {name}...", end=" ", flush=True)
        oof = cross_val_predict(model, X, y, cv=CV, method="predict_proba", n_jobs=-1)[:, 1]
        metrics = evaluate_oof(y, oof, name)
        results[f"Baseline_{name}"] = metrics
        print(f"AUC={metrics['AUC-ROC']:.4f}")

    return results, X, y, prep_time


def run_feast_pipeline() -> tuple[dict, pd.DataFrame, pd.Series, float]:
    """Run Feast-based pipeline: retrieve features via get_historical_features()."""
    from feast import FeatureStore

    store = FeatureStore(repo_path=str(FEAST_REPO))

    # Load labels (entity_df for point-in-time join)
    labels_path = FEAST_REPO / "data" / "labels.parquet"
    entity_df = pd.read_parquet(labels_path)
    entity_df["order_id"] = entity_df["order_id"].astype(str)

    # Feature references
    feature_refs = [
        # Raw features
        "order_raw_features:num_drivers",
        "order_raw_features:num_orders",
        "order_raw_features:eta_avg",
        "order_raw_features:eta_std",
        "order_raw_features:eta_min",
        "order_raw_features:eda_avg",
        "order_raw_features:eda_std",
        "order_raw_features:eda_min",
        "order_raw_features:distance",
        "order_raw_features:total_fee",
        "order_raw_features:hour_of_day",
        "order_raw_features:minute_of_hour",
        "order_raw_features:rush_hour",
        "order_raw_features:user_waiting_time_seconds",
        # Derived features
        "order_derived_features:supply_demand_ratio",
        "order_derived_features:demand_supply_ratio",
        "order_derived_features:eta_confidence",
        "order_derived_features:eda_confidence",
        "order_derived_features:fee_per_km",
        "order_derived_features:eta_per_km",
        "order_derived_features:eta_eda_ratio",
        "order_derived_features:pickup_to_trip_ratio",
        "order_derived_features:is_short_trip",
        "order_derived_features:is_long_eta",
        "order_derived_features:is_high_wait",
        "order_derived_features:is_negative_wait",
        "order_derived_features:is_single_driver",
        "order_derived_features:day_of_week",
        "order_derived_features:is_weekend",
        "order_derived_features:is_friday",
        "order_derived_features:rush_hour_weekday",
        # On-demand (computed at retrieval)
        "on_demand_interactions:hour_sin",
        "on_demand_interactions:hour_cos",
        "on_demand_interactions:minutes_since_midnight",
        "on_demand_interactions:short_trip_rush",
        "on_demand_interactions:low_supply_flag",
        "on_demand_interactions:low_supply_short_trip",
        "on_demand_interactions:high_eta_rush",
    ]

    print("  Retrieving historical features from Feast...", flush=True)
    t0 = time.time()
    training_df = store.get_historical_features(
        entity_df=entity_df[["order_id", "event_timestamp"]],
        features=feature_refs,
    ).to_df()
    retrieval_time = time.time() - t0
    print(f"  Retrieved {len(training_df):,} rows, {len(training_df.columns)} cols in {retrieval_time:.1f}s")

    # Merge labels
    training_df = training_df.merge(
        entity_df[["order_id", "is_completed"]],
        on="order_id",
        how="inner",
    )

    # Drop non-feature columns
    drop_cols = ["order_id", "event_timestamp"]
    X = training_df.drop(columns=[c for c in drop_cols + ["is_completed"] if c in training_df.columns])
    y = training_df["is_completed"]

    # Drop any all-null columns
    null_cols = X.columns[X.isnull().all()].tolist()
    if null_cols:
        X = X.drop(columns=null_cols)
        print(f"  Dropped all-null columns: {null_cols}")

    # Fill remaining NaN with 0
    X = X.fillna(0)

    print(f"  Feature matrix: {X.shape}")

    results = {}
    for name, model in [("LightGBM", create_lgb(N_EST)), ("XGBoost", create_xgb(N_EST))]:
        print(f"  Feast {name}...", end=" ", flush=True)
        oof = cross_val_predict(model, X, y, cv=CV, method="predict_proba", n_jobs=-1)[:, 1]
        metrics = evaluate_oof(y, oof, name)
        results[f"Feast_{name}"] = metrics
        print(f"AUC={metrics['AUC-ROC']:.4f}")

    return results, X, y, retrieval_time


def run_comparison(data_path: str | None = None, sep: str = "\t"):
    """Run full comparison: Baseline vs Feast pipeline."""
    if data_path is None:
        data_path = str(PROJECT_ROOT / "data" / "raw" / "Completion_prediction__dataset__hashing_500k.parquet")

    all_results = {}

    # ── Baseline ──
    print("\n" + "=" * 60)
    print("BASELINE: Direct pandas feature engineering")
    print("=" * 60)
    baseline_results, X_base, y_base, baseline_time = run_baseline(data_path, sep)
    all_results.update(baseline_results)

    # ── Feast ──
    print("\n" + "=" * 60)
    print("FEAST: Feature Store retrieval")
    print("=" * 60)
    feast_results, X_feast, y_feast, feast_time = run_feast_pipeline()
    all_results.update(feast_results)

    # ── Comparison ──
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    comparison = compare_models(all_results)
    print(comparison.to_string())

    print(f"\nData preparation time:")
    print(f"  Baseline (pandas): {baseline_time:.1f}s")
    print(f"  Feast retrieval:   {feast_time:.1f}s")
    print(f"  Overhead:          {feast_time - baseline_time:+.1f}s")

    print(f"\nFeature counts:")
    print(f"  Baseline: {X_base.shape[1]} features")
    print(f"  Feast:    {X_feast.shape[1]} features")

    # Feature importance comparison
    from sklearn.ensemble import GradientBoostingClassifier
    import lightgbm as lgb

    lgb_model = create_lgb(N_EST)
    lgb_model.fit(X_feast, y_feast)
    fi = pd.DataFrame({
        "feature": X_feast.columns,
        "importance": lgb_model.feature_importances_,
    }).sort_values("importance", ascending=False)
    print(f"\nTop 10 features (Feast LightGBM):")
    print(fi.head(10).to_string(index=False))

    return {
        "comparison": comparison,
        "baseline_time": baseline_time,
        "feast_time": feast_time,
        "feature_importance": fi,
    }


if __name__ == "__main__":
    run_comparison()
