"""
Improvement Experiments — So sánh 3 cải tiến vs baseline
=========================================================
Exp 0: Baseline (kết quả hiện tại)
Exp 1: + Target encoding hour_of_day
Exp 2: + Calibrated XGB/LGB trong Stacking
Exp 3: + Optuna tuning RF

Chạy lần lượt, so sánh tất cả trong 1 bảng.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import StackingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from src.data.preprocessing import load_data, preprocess, get_X_y
from src.features.transformations import build_features
from src.models.lightgbm_model import create_model as create_lgb
from src.models.xgboost_model import create_model as create_xgb
from src.models.random_forest_model import create_model as create_rf
from src.models.ensemble import create_stacking_model
from src.evaluation.metrics import evaluate_oof, compare_models

SEED = 42
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
N_EST = 500


# ═══════════════════════════════════════════════════════════════
# DATA PREPARATION (shared across all experiments)
# ═══════════════════════════════════════════════════════════════

def prepare_data(data_path: str, sep: str = "\t"):
    """Load, preprocess, feature engineer. Returns X, y, driver_ids."""
    df = load_data(data_path, sep=sep)
    # Lưu driver_id trước khi preprocess drop nó
    driver_ids = df["driver_id"].copy() if "driver_id" in df.columns else None
    df = preprocess(df)
    df = build_features(df)
    X, y = get_X_y(df)
    return X, y, driver_ids


# ═══════════════════════════════════════════════════════════════
# TARGET ENCODING (cross-validated to avoid leakage)
# ═══════════════════════════════════════════════════════════════

def add_target_encoding_cv(X: pd.DataFrame, y: pd.Series, col: str, cv, smoothing: int = 10):
    """
    Cross-validated target encoding.
    Trong mỗi fold: tính mean(target) per category từ training data,
    áp dụng lên validation data. Smoothing để tránh overfit giờ ít data.
    """
    global_mean = y.mean()
    encoded = pd.Series(index=X.index, dtype=float, name=f"{col}_target_enc")

    for train_idx, val_idx in cv.split(X, y):
        # Tính target mean per category trên training fold
        train_df = pd.DataFrame({col: X.iloc[train_idx][col], "target": y.iloc[train_idx]})
        stats = train_df.groupby(col)["target"].agg(["mean", "count"])

        # Smoothed mean: (count * mean + smoothing * global_mean) / (count + smoothing)
        stats["smoothed"] = (stats["count"] * stats["mean"] + smoothing * global_mean) / (stats["count"] + smoothing)

        # Map lên validation fold
        mapping = stats["smoothed"].to_dict()
        encoded.iloc[val_idx] = X.iloc[val_idx][col].map(mapping).fillna(global_mean)

    return encoded


# ═══════════════════════════════════════════════════════════════
# EXPERIMENT RUNNER
# ═══════════════════════════════════════════════════════════════

def eval_models(X, y, models: dict, cv) -> dict:
    """Run CV for each model, return {name: metrics_dict}."""
    results = {}
    for name, model in models.items():
        print(f"  {name}...", end=" ", flush=True)
        oof = cross_val_predict(model, X, y, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
        metrics = evaluate_oof(y, oof, name)
        results[name] = metrics
        print(f"AUC={metrics['AUC-ROC']:.4f}")
    return results


def run_all_experiments(data_path: str, sep: str = "\t"):
    """Run all experiments and return comparison DataFrame."""

    X_base, y, driver_ids = prepare_data(data_path, sep)
    all_results = {}

    # ── EXP 0: BASELINE ──
    print("\n" + "=" * 60)
    print("EXP 0: BASELINE (current)")
    print("=" * 60)
    baseline_models = {
        "LightGBM": create_lgb(N_EST),
        "XGBoost": create_xgb(N_EST),
        "RandomForest": create_rf(),  # dùng default = Optuna best (672 cây), không override
    }
    exp0 = eval_models(X_base, y, baseline_models, CV)

    # Stacking baseline
    print("  Stacking...", end=" ", flush=True)
    stacking_base = create_stacking_model(N_EST)
    oof_stack = cross_val_predict(stacking_base, X_base, y, cv=CV, method="predict_proba", n_jobs=1)[:, 1]
    exp0["Stacking"] = evaluate_oof(y, oof_stack, "Stacking")
    print(f"AUC={exp0['Stacking']['AUC-ROC']:.4f}")

    for name, metrics in exp0.items():
        all_results[f"Baseline_{name}"] = metrics

    # ── EXP 1: + TARGET ENCODING HOUR ──
    print("\n" + "=" * 60)
    print("EXP 1: + Target Encoding hour_of_day")
    print("=" * 60)
    X_te = X_base.copy()
    X_te["hour_target_enc"] = add_target_encoding_cv(X_base, y, "hour_of_day", CV, smoothing=10)
    print(f"  Added hour_target_enc (smoothing=10)")

    exp1 = eval_models(X_te, y, {
        "LightGBM": create_lgb(N_EST),
        "XGBoost": create_xgb(N_EST),
        "RandomForest": create_rf(),  # dùng default = Optuna best (672 cây), không override
    }, CV)

    print("  Stacking...", end=" ", flush=True)
    stacking_te = create_stacking_model(N_EST)
    oof_te = cross_val_predict(stacking_te, X_te, y, cv=CV, method="predict_proba", n_jobs=1)[:, 1]
    exp1["Stacking"] = evaluate_oof(y, oof_te, "Stacking")
    print(f"AUC={exp1['Stacking']['AUC-ROC']:.4f}")

    for name, metrics in exp1.items():
        all_results[f"TargetEnc_{name}"] = metrics

    # ── EXP 2: + CALIBRATED STACKING ──
    print("\n" + "=" * 60)
    print("EXP 2: + Calibrated XGB/LGB in Stacking")
    print("=" * 60)
    cal_stacking = StackingClassifier(
        estimators=[
            ("lgb_cal", CalibratedClassifierCV(create_lgb(N_EST), cv=3, method="isotonic")),
            ("xgb_cal", CalibratedClassifierCV(create_xgb(N_EST), cv=3, method="isotonic")),
            ("rf", create_rf()),  # RF already well-calibrated; dùng default = Optuna best (672 cây)
        ],
        final_estimator=LogisticRegression(max_iter=1000, random_state=SEED),
        cv=5,
        stack_method="predict_proba",
        passthrough=False,
        n_jobs=1,
    )
    print("  CalibratedStacking...", end=" ", flush=True)
    oof_cal = cross_val_predict(cal_stacking, X_base, y, cv=CV, method="predict_proba", n_jobs=1)[:, 1]
    exp2_metrics = evaluate_oof(y, oof_cal, "CalibratedStacking")
    print(f"AUC={exp2_metrics['AUC-ROC']:.4f}")
    all_results["CalStacking"] = exp2_metrics

    # ── EXP 3: OPTUNA TUNED RF ──
    print("\n" + "=" * 60)
    print("EXP 3: Optuna Tuned RandomForest")
    print("=" * 60)
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def rf_objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 200, 800),
                "max_depth": trial.suggest_int("max_depth", 6, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 30),
                "min_samples_split": trial.suggest_int("min_samples_split", 10, 50),
                "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", 0.3, 0.5]),
                "random_state": SEED,
                "n_jobs": -1,
            }
            rf = RandomForestClassifier(**params)
            oof = cross_val_predict(rf, X_base, y, cv=CV, method="predict_proba", n_jobs=-1)[:, 1]
            from sklearn.metrics import roc_auc_score
            return roc_auc_score(y, oof)

        print("  Tuning (50 trials)...", flush=True)
        study = optuna.create_study(direction="maximize")
        study.optimize(rf_objective, n_trials=50, show_progress_bar=False)

        print(f"  Best params: {study.best_params}")
        print(f"  Best AUC: {study.best_value:.4f}")

        # Evaluate tuned RF
        best_rf = RandomForestClassifier(**study.best_params, random_state=SEED, n_jobs=-1)
        print("  TunedRF...", end=" ", flush=True)
        oof_tuned = cross_val_predict(best_rf, X_base, y, cv=CV, method="predict_proba", n_jobs=-1)[:, 1]
        exp3_metrics = evaluate_oof(y, oof_tuned, "TunedRF")
        print(f"AUC={exp3_metrics['AUC-ROC']:.4f}")
        all_results["TunedRF"] = exp3_metrics

        # Save best params
        best_params = study.best_params

    except ImportError:
        print("  optuna not installed. pip install optuna")
        best_params = None

    # ── EXP 4: + DRIVER_ID CV TARGET ENCODING ──
    if driver_ids is not None and len(X_base) > 10000:
        print("\n" + "=" * 60)
        print("EXP 4: + Driver ID CV Target Encoding (smoothing=30)")
        print("=" * 60)

        # Thêm driver_id tạm vào X để tính target encoding
        X_drv = X_base.copy()
        X_drv["_driver_id"] = driver_ids.values

        driver_te = add_target_encoding_cv(X_drv, y, "_driver_id", CV, smoothing=30)
        X_drv["driver_completion_rate_cv"] = driver_te

        # Tính driver order count (không leak — chỉ count, không dùng target)
        driver_counts = driver_ids.value_counts()
        X_drv["driver_order_count"] = driver_ids.map(driver_counts).values

        X_drv = X_drv.drop(columns=["_driver_id"])
        print(f"  Added: driver_completion_rate_cv, driver_order_count")

        exp4 = eval_models(X_drv, y, {
            "LightGBM": create_lgb(N_EST),
            "XGBoost": create_xgb(N_EST),
            "RandomForest": create_rf(),
        }, CV)

        for name, metrics in exp4.items():
            all_results[f"DriverTE_{name}"] = metrics
    else:
        print("\n  Skipped EXP 4 (no driver_id or dataset too small)")

    # ── COMPARISON ──
    print("\n" + "=" * 60)
    print("FINAL COMPARISON")
    print("=" * 60)
    comparison = compare_models(all_results)
    print(comparison.to_string())

    return {
        "comparison": comparison,
        "all_results": all_results,
        "best_optuna_params": best_params if 'best_params' in dir() else None,
    }


if __name__ == "__main__":
    data_path = PROJECT_ROOT / "data" / "raw" / "Completion_prediction__dataset__hashing_500k.parquet"
    run_all_experiments(str(data_path))
