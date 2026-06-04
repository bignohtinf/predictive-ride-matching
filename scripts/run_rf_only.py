"""
Chạy chỉ RandomForest với Optuna best params.
Bỏ qua LightGBM, XGBoost, Stacking để tiết kiệm time.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import warnings
warnings.filterwarnings("ignore")

from pipelines.training.pipeline import run_pipeline

DATA_PATH = PROJECT_ROOT / "data" / "raw" / "Completion_prediction__dataset__hashing.csv"

print("=" * 60)
print("RandomForest only — Optuna best params (no override)")
print("=" * 60)

results = run_pipeline(
    data_path=str(DATA_PATH),
    sep="\t",
    # n_estimators KHÔNG truyền → mặc định 500 chỉ cho LGB/XGB
    # RF luôn dùng create_rf() với default params (Optuna best: 672 cây)
    cv_folds=5,
    save=True,
    models_to_run=["RandomForest"],  # bỏ qua LGB, XGB, Stacking
)

print("\n" + "=" * 60)
print("FINAL RESULT")
print("=" * 60)
print(results["results_df"].to_string())
