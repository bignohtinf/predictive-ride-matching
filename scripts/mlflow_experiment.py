import argparse
import os
import sys
import time
import warnings
from pathlib import Path

import mlflow
import mlflow.lightgbm
import mlflow.sklearn
import mlflow.xgboost
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.calibration import CalibratedClassifierCV  # noqa: F401 (reserved for future use)
from sklearn.ensemble import RandomForestClassifier  # noqa: F401 (kept for optional re-add)
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ensure UTF-8 output on Windows (avoid cp1252 UnicodeEncodeError)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# -- ensure src importable from project root -----------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocessing import get_X_y, load_data, preprocess
from src.features.transformations import build_features

# -- Constants -----------------------------------------------------------------
EXPERIMENT_NAME = "crp-model-comparison"
DATA_PATH = str(PROJECT_ROOT / "data/raw/Completion_prediction__dataset__hashing_500k.parquet")
SEED = 42
SAMPLE_SIZE = 100_000   # 100k sample: fast enough, still representative


# -- Helpers -------------------------------------------------------------------

def ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error."""
    bins = np.linspace(0, 1, n_bins + 1)
    ece_val = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        ece_val += (mask.sum() / len(y_true)) * abs(y_true[mask].mean() - y_prob[mask].mean())
    return float(ece_val)


def compute_metrics(y_true, y_prob) -> dict:
    y_pred = (y_prob >= 0.5).astype(int)
    return {
        "auc_roc":  float(roc_auc_score(y_true, y_prob)),
        "auc_pr":   float(average_precision_score(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob)),
        "f1":       float(f1_score(y_true, y_pred)),
        "ece":      ece(y_true.values if hasattr(y_true, "values") else y_true, y_prob),
    }


def load_and_prepare(data_path: str, sample_size: int | None = SAMPLE_SIZE):
    """Load parquet -> preprocess -> feature engineering -> train/val/test split."""
    print("=" * 60)
    print(f"[DATA] Loading: {data_path}")
    df = load_data(data_path)

    if sample_size and len(df) > sample_size:
        df = df.sample(sample_size, random_state=SEED)
        print(f"[DATA] Sampled -> {len(df):,} rows")

    print("\n[PREP] Preprocessing...")
    df = preprocess(df)

    print("\n[FEAT] Feature engineering...")
    df = build_features(df)

    X, y = get_X_y(df)
    print(f"\n[OK] Features: {X.shape[1]}  |  Positive rate: {y.mean():.3f}")

    # 70 / 15 / 15 stratified split
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=SEED, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=SEED, stratify=y_temp
    )
    print(f"[SPLIT] Train {len(X_train):,} | Val {len(X_val):,} | Test {len(X_test):,}")
    return X_train, X_val, X_test, y_train, y_val, y_test


# -- Model definitions ---------------------------------------------------------

MODELS = {
    "LightGBM": LGBMClassifier(
        n_estimators=300,
        num_leaves=63,
        learning_rate=0.05,
        max_depth=10,
        min_child_samples=50,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=SEED,
        verbose=-1,
        n_jobs=-1,
    ),
    "XGBoost": XGBClassifier(
        n_estimators=300,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        eval_metric="logloss",
        random_state=SEED,
        n_jobs=-1,
        verbosity=0,
    ),
}


def fit_model(name: str, model, X_train, y_train, X_val, y_val):
    """Fit with early stopping for LGB/XGB, plain fit for others."""
    if name == "LightGBM":
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[early_stopping(40, verbose=False), log_evaluation(period=-1)],
        )
    elif name == "XGBoost":
        model.set_params(early_stopping_rounds=40)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    else:
        model.fit(X_train, y_train)
    return model


# -- Single run ----------------------------------------------------------------

def run_experiment(name, model, X_train, y_train, X_val, y_val, X_test, y_test):
    """Train one model, log everything to MLflow, return test metrics."""
    print(f"\n{'=' * 60}")
    print(f"[RUN] {name}")

    with mlflow.start_run(run_name=name) as run:
        mlflow.set_tag("model_type", name)
        mlflow.set_tag("dataset", "crp_500k_sample100k")

        # Log hyperparams (skip nested dicts / non-serializable)
        params = {k: v for k, v in model.get_params().items()
                  if not isinstance(v, dict)}
        mlflow.log_params(params)

        # Train
        t0 = time.time()
        model = fit_model(name, model, X_train, y_train, X_val, y_val)
        train_sec = round(time.time() - t0, 2)
        mlflow.log_metric("train_time_seconds", train_sec)
        print(f"  Trained in {train_sec}s")

        # Val metrics (raw predict_proba — LGB/XGB are well-calibrated natively)
        val_prob = model.predict_proba(X_val)[:, 1]
        val_m = compute_metrics(y_val, val_prob)
        for k, v in val_m.items():
            mlflow.log_metric(f"val_{k}", round(v, 6))

        # Test metrics (holdout)
        test_prob = model.predict_proba(X_test)[:, 1]
        test_m = compute_metrics(y_test, test_prob)
        for k, v in test_m.items():
            mlflow.log_metric(f"test_{k}", round(v, 6))

        print(f"  AUC-ROC={test_m['auc_roc']:.4f}  "
              f"LogLoss={test_m['log_loss']:.4f}  "
              f"F1={test_m['f1']:.4f}  "
              f"ECE={test_m['ece']:.4f}")

        # --- Artifact: model (MLflow native format) ---
        if name == "LightGBM":
            mlflow.lightgbm.log_model(model, artifact_path="model")
        elif name == "XGBoost":
            mlflow.xgboost.log_model(model, artifact_path="model")
        else:
            mlflow.sklearn.log_model(model, artifact_path="model")

        # Artifact: feature list
        out_dir = PROJECT_ROOT / "data/models"
        out_dir.mkdir(parents=True, exist_ok=True)
        feat_file = out_dir / f"{name}_features.txt"
        feat_file.write_text("\n".join(X_train.columns.tolist()), encoding="utf-8")
        mlflow.log_artifact(str(feat_file), artifact_path="features")

        # Artifact: metrics CSV
        metrics_csv = out_dir / f"{name}_metrics.csv"
        pd.DataFrame([
            {"split": "val",  **val_m},
            {"split": "test", **test_m},
        ]).to_csv(metrics_csv, index=False)
        mlflow.log_artifact(str(metrics_csv), artifact_path="metrics")

        print(f"  Run ID: {run.info.run_id}")
        return test_m, run.info.run_id


# -- Main ----------------------------------------------------------------------

def main(args):
    # MLflow setup
    # New MLflow versions deprecate file store -> use SQLite backend
    db_path = PROJECT_ROOT / "mlflow.db"
    tracking_uri = f"sqlite:///{db_path.as_posix()}"
    mlflow.set_tracking_uri(tracking_uri)

    if args.s3_artifacts:
        artifact_root = f"s3://{args.s3_bucket}/mlflow"
        os.environ.setdefault("MLFLOW_ARTIFACT_ROOT", artifact_root)
        print(f"[S3] Artifact store: {artifact_root}")
    else:
        print(f"[MLFLOW] Tracking URI: {tracking_uri}")

    mlflow.set_experiment(EXPERIMENT_NAME)
    print(f"[MLFLOW] Experiment: {EXPERIMENT_NAME}")

    # Data
    sample = None if args.full_data else SAMPLE_SIZE
    X_train, X_val, X_test, y_train, y_val, y_test = load_and_prepare(
        args.data, sample_size=sample
    )

    # Run all 3 models
    results = {}
    for name, model in MODELS.items():
        test_m, rid = run_experiment(
            name, model,
            X_train, y_train, X_val, y_val, X_test, y_test
        )
        results[name] = {**test_m, "run_id": rid}

    # Summary
    print(f"\n{'=' * 60}")
    print("FINAL COMPARISON -- Test Set Metrics")
    print("=" * 60)
    summary = pd.DataFrame(results).T.drop(columns=["run_id"])
    summary = summary.sort_values("auc_roc", ascending=False)
    print(summary.to_string(float_format=lambda x: f"{x:.4f}"))

    # Save comparison CSV
    csv_out = PROJECT_ROOT / "data/models/model_comparison_results.csv"
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(csv_out, encoding="utf-8")
    print(f"\nResults saved -> {csv_out}")

    # Log summary run
    with mlflow.start_run(run_name="__comparison_summary__"):
        mlflow.set_tag("type", "summary")
        mlflow.log_artifact(str(csv_out), artifact_path="comparison")
        best = summary.iloc[0]
        mlflow.log_metric("best_auc_roc",  round(float(best["auc_roc"]), 6))
        mlflow.log_metric("best_log_loss", round(float(best["log_loss"]), 6))
        mlflow.log_metric("best_f1",       round(float(best["f1"]), 6))

    winner = summary.index[0]
    print(f"\nBest model: {winner}  (AUC-ROC = {summary.loc[winner, 'auc_roc']:.4f})")
    print(f"\nOpen MLflow UI:")
    print(f"  .\\venv\\Scripts\\python.exe -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000")
    print(f"  -> http://127.0.0.1:5000\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRP MLflow Model Comparison")
    parser.add_argument("--data", default=DATA_PATH)
    parser.add_argument("--full-data", action="store_true",
                        help="Use full 500k (slow); default: 100k sample")
    parser.add_argument("--s3-artifacts", action="store_true",
                        help="Upload artifacts to S3")
    parser.add_argument("--s3-bucket", default="mlops-lab-wine-quality-bignoht")
    args = parser.parse_args()
    main(args)
