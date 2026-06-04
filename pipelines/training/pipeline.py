"""
Training Pipeline — Orchestrates data loading → preprocessing → feature engineering
→ model training (CV) → evaluation → save artifacts.

Gọi từ notebook hoặc command line.

MLflow tracking được bật tự động nếu env var MLFLOW_TRACKING_URI được set.
Với SageMaker Managed MLflow, set MLFLOW_TRACKING_URI=<tracking-server-arn>
và cài sagemaker-mlflow package.
"""

import os
import sys
from pathlib import Path

import mlflow
import mlflow.lightgbm
import mlflow.sklearn
import mlflow.xgboost
import numpy as np
import joblib
from sklearn.model_selection import StratifiedKFold, cross_val_predict

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocessing import load_data, preprocess, get_X_y
from src.features.transformations import build_features
from src.models.lightgbm_model import create_model as create_lgb
from src.models.xgboost_model import create_model as create_xgb
from src.models.random_forest_model import create_model as create_rf
from src.models.ensemble import create_stacking_model
from src.evaluation.metrics import evaluate_oof, print_evaluation, compare_models


SEED = 42
CV_FOLDS = 5
N_ESTIMATORS = 500
MODEL_OUTPUT_DIR = PROJECT_ROOT / "data" / "models"
MLFLOW_EXPERIMENT = "crp-completion-rate-prediction"

# Flavour loggers per model name
_MLFLOW_FLAVOR = {
    "LightGBM": mlflow.lightgbm,
    "XGBoost": mlflow.xgboost,
}


def _mlflow_active() -> bool:
    """True nếu MLFLOW_TRACKING_URI được set."""
    uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if not uri:
        return False
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    return True


def run_pipeline(
    data_path: str,
    sep: str = "\t",
    n_estimators: int = N_ESTIMATORS,
    cv_folds: int = CV_FOLDS,
    save: bool = True,
    models_to_run: list | None = None,  # None = chạy tất cả; ví dụ: ['RandomForest']
) -> dict:
    """
    Run full training pipeline.

    Returns:
        dict with keys: X, y, features, models, oof_predictions, cv_results, results_df
    """
    # ── 1. Load ──
    print("=" * 60)
    print("STEP 1: Load Data")
    print("=" * 60)
    df = load_data(data_path, sep=sep)

    # ── 2. Preprocess ──
    print("\n" + "=" * 60)
    print("STEP 2: Preprocessing")
    print("=" * 60)
    df = preprocess(df)

    # ── 3. Feature Engineering ──
    print("\n" + "=" * 60)
    print("STEP 3: Feature Engineering")
    print("=" * 60)
    df = build_features(df)

    # ── 4. Prepare X, y ──
    X, y = get_X_y(df)
    features = list(X.columns)
    print(f"\nReady: {X.shape[0]} samples, {len(features)} features")
    print(f"Target: {y.value_counts().to_dict()}")

    # ── 5. Define models ──
    all_models = {
        "LightGBM": create_lgb(n_estimators),
        "XGBoost": create_xgb(n_estimators),
        "RandomForest": create_rf(),  # dùng Optuna best params (default), không override n_estimators
    }
    models = {
        name: m for name, m in all_models.items()
        if models_to_run is None or name in models_to_run
    }

    # In tham số từng model
    print("\nModel parameters:")
    for name, m in models.items():
        params = m.get_params()
        print(f"  [{name}]")
        for k, v in params.items():
            print(f"    {k}: {v}")

    # ── 6. Cross-validation base models ──
    print("\n" + "=" * 60)
    print("STEP 4: Cross-Validation (Base Models)")
    print("=" * 60)

    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=SEED)
    oof_predictions = {}
    cv_results = {}

    for name, model in models.items():
        print(f"\nTraining {name}...")
        oof_proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
        oof_predictions[name] = oof_proba
        cv_results[name] = evaluate_oof(y, oof_proba, name)
        print(f"  AUC-ROC: {cv_results[name]['AUC-ROC']:.4f}  |  Log Loss: {cv_results[name]['Log Loss']:.4f}  |  F1: {cv_results[name]['F1']:.4f}")

    # ── 7. Stacking Ensemble ──
    run_stacking = models_to_run is None or "Stacking" in models_to_run
    if run_stacking:
        print("\n" + "=" * 60)
        print("STEP 5: Stacking Ensemble")
        print("=" * 60)
        print("Training Stacking (this may take a while)...")

        stacking_model = create_stacking_model(n_estimators)
        stacking_oof = cross_val_predict(stacking_model, X, y, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
        oof_predictions["Stacking"] = stacking_oof
        cv_results["Stacking"] = evaluate_oof(y, stacking_oof, "Stacking")
        print(f"  AUC-ROC: {cv_results['Stacking']['AUC-ROC']:.4f}  |  Log Loss: {cv_results['Stacking']['Log Loss']:.4f}  |  F1: {cv_results['Stacking']['F1']:.4f}")
    else:
        print("\n[Stacking skipped]")

    # ── 8. Compare ──
    print("\n" + "=" * 60)
    print("STEP 6: Results")
    print("=" * 60)
    results_df = compare_models(cv_results)
    print(results_df.to_string())

    # ── 9. Train final models on full data & save ──
    if save:
        print("\n" + "=" * 60)
        print("STEP 7: Save Artifacts")
        print("=" * 60)

        MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        use_mlflow = _mlflow_active()
        if use_mlflow:
            print("  MLflow tracking: ON")
        else:
            print("  MLflow tracking: OFF (set MLFLOW_TRACKING_URI to enable)")

        # Train từng model trên full data
        import pickle
        import pandas as pd

        trained_models = {}
        mlflow_run_ids = {}
        all_factories = [
            ("LightGBM", lambda: create_lgb(n_estimators)),
            ("XGBoost", lambda: create_xgb(n_estimators)),
            ("RandomForest", lambda: create_rf()),
        ]
        for name, model_factory in [
            (n, f) for n, f in all_factories
            if models_to_run is None or n in models_to_run
        ]:
            m = model_factory()
            m.fit(X, y)
            trained_models[name] = m

            model_path = MODEL_OUTPUT_DIR / f"{name}.pkl"
            with open(model_path, "wb") as f:
                pickle.dump({"model": m, "features": features, "cv_metrics": cv_results[name]}, f)
            print(f"  Saved: {model_path}")

            if use_mlflow:
                flavor = _MLFLOW_FLAVOR.get(name, mlflow.sklearn)
                with mlflow.start_run(run_name=name) as run:
                    mlflow.log_params({k: v for k, v in m.get_params().items() if v is not None})
                    mlflow.log_metrics(cv_results[name])
                    mlflow.set_tag("model_name", name)
                    flavor.log_model(m, artifact_path="model")
                    mlflow.log_artifact(str(model_path), artifact_path="pkl")
                    mlflow_run_ids[name] = run.info.run_id
                    print(f"  MLflow run logged: {name} ({run.info.run_id[:8]})")

        # Train stacking on full data
        if run_stacking:
            stacking_full = create_stacking_model(n_estimators)
            stacking_full.fit(X, y)
            trained_models["Stacking"] = stacking_full
            stacking_path = MODEL_OUTPUT_DIR / "Stacking.pkl"
            with open(stacking_path, "wb") as f:
                pickle.dump({"model": stacking_full, "features": features, "cv_metrics": cv_results["Stacking"]}, f)
            print(f"  Saved: {stacking_path}")

            if use_mlflow:
                with mlflow.start_run(run_name="Stacking") as run:
                    mlflow.log_metrics(cv_results["Stacking"])
                    mlflow.set_tag("model_name", "Stacking")
                    mlflow.sklearn.log_model(stacking_full, artifact_path="model")
                    mlflow.log_artifact(str(stacking_path), artifact_path="pkl")
                    mlflow_run_ids["Stacking"] = run.info.run_id
                    print(f"  MLflow run logged: Stacking ({run.info.run_id[:8]})")

        # Feature importance (LightGBM nếu có, nếu không thì dùng RF)
        fi_model_name = "LightGBM" if "LightGBM" in trained_models else ("RandomForest" if "RandomForest" in trained_models else None)
        if fi_model_name:
            importance = pd.DataFrame({
                "feature": features,
                "importance": trained_models[fi_model_name].feature_importances_,
            }).sort_values("importance", ascending=False)
        else:
            importance = pd.DataFrame()

        # Save tổng hợp
        artifacts = {
            "trained_models": trained_models,
            "features": features,
            "cv_results": cv_results,
            "feature_importance": importance,
        }
        artifact_path = MODEL_OUTPUT_DIR / "model_artifacts.joblib"
        joblib.dump(artifacts, artifact_path)
        print(f"  Saved: {artifact_path}")

        # Đánh tag champion model trong MLflow
        if use_mlflow and mlflow_run_ids:
            best = results_df.index[0]
            champion_run_id = mlflow_run_ids.get(best)
            if champion_run_id:
                with mlflow.start_run(run_id=champion_run_id):
                    mlflow.set_tag("champion", "true")
                print(f"  MLflow champion tagged: {best}")

    best = results_df.index[0]
    print(f"\nBest: {best} (AUC-ROC = {results_df.loc[best, 'AUC-ROC']:.4f})")

    return {
        "X": X,
        "y": y,
        "features": features,
        "models": models,
        "oof_predictions": oof_predictions,
        "cv_results": cv_results,
        "results_df": results_df,
    }


if __name__ == "__main__":
    data_path = PROJECT_ROOT / "data" / "raw" / "Completion_prediction__dataset__hashing.csv"
    run_pipeline(str(data_path))
