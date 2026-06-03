"""Evaluation metrics for completion rate prediction."""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    log_loss,
    precision_score,
    recall_score,
    f1_score,
)
from loguru import logger


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        if mask.sum() == 0:
            continue

        bin_acc = y_true[mask].mean()
        bin_conf = y_prob[mask].mean()
        bin_size = mask.sum() / len(y_true)
        ece += bin_size * abs(bin_acc - bin_conf)

    return ece


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series, calibrator=None) -> dict:
    """Compute all evaluation metrics."""
    raw_probs = model.predict(X_test)

    if calibrator is not None:
        if hasattr(calibrator, "predict"):
            probs = calibrator.predict(raw_probs)
        else:
            probs = calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
    else:
        probs = raw_probs

    preds = (probs > 0.5).astype(int)

    metrics = {
        "auc_roc": roc_auc_score(y_test, probs),
        "auc_pr": average_precision_score(y_test, probs),
        "log_loss": log_loss(y_test, probs),
        "ece": expected_calibration_error(y_test.values, probs),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
        "completion_rate_actual": y_test.mean(),
        "completion_rate_predicted": probs.mean(),
    }

    # Precision at bottom-k (lowest predicted probability)
    k = min(100, len(probs))
    bottom_k_idx = np.argsort(probs)[:k]
    metrics["precision_at_bottom_100"] = 1 - y_test.iloc[bottom_k_idx].mean()

    return metrics
