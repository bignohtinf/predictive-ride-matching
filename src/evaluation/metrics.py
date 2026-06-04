"""Evaluation metrics for CRP models."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    log_loss,
    f1_score,
    classification_report,
    confusion_matrix,
)


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_prob[mask].mean()
        ece += (mask.sum() / len(y_true)) * abs(bin_acc - bin_conf)
    return ece


def evaluate_oof(y_true: pd.Series, oof_proba: np.ndarray, name: str = "") -> dict:
    """Evaluate out-of-fold predictions. Returns dict of metrics."""
    preds = (oof_proba > 0.5).astype(int)
    metrics = {
        "AUC-ROC": roc_auc_score(y_true, oof_proba),
        "AUC-PR": average_precision_score(y_true, oof_proba),
        "Log Loss": log_loss(y_true, oof_proba),
        "F1": f1_score(y_true, preds),
        "ECE": expected_calibration_error(y_true.values, oof_proba),
    }
    return metrics


def print_evaluation(y_true: pd.Series, oof_proba: np.ndarray, name: str = "Model"):
    """Print evaluation metrics và classification report."""
    metrics = evaluate_oof(y_true, oof_proba, name)
    preds = (oof_proba > 0.5).astype(int)

    print(f"\n{'='*50}")
    print(f" {name}")
    print(f"{'='*50}")
    for k, v in metrics.items():
        print(f"  {k:12s}: {v:.4f}")
    print()
    print(classification_report(y_true, preds, target_names=["Not Completed", "Completed"]))
    return metrics


def compare_models(results: dict[str, dict]) -> pd.DataFrame:
    """So sánh metrics giữa các models, trả về DataFrame sorted by AUC-ROC."""
    df = pd.DataFrame(results).T
    return df.sort_values("AUC-ROC", ascending=False)
