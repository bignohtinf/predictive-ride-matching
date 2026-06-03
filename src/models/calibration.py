"""Probability calibration for model outputs."""

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from loguru import logger


class LGBMWrapper:
    """Wrapper to make LightGBM compatible with sklearn calibration."""

    def __init__(self, model):
        self.model = model
        self.classes_ = np.array([0, 1])

    def predict_proba(self, X):
        preds = self.model.predict(X)
        return np.column_stack([1 - preds, preds])

    def predict(self, X):
        return (self.model.predict(X) > 0.5).astype(int)


def calibrate_model(model, X_val: pd.DataFrame, y_val: pd.Series, method: str = "isotonic"):
    """Calibrate model probabilities using validation set."""
    raw_probs = model.predict(X_val)

    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_probs, y_val)
    elif method == "platt":
        calibrator = LogisticRegression()
        calibrator.fit(raw_probs.reshape(-1, 1), y_val)
    else:
        raise ValueError(f"Unknown calibration method: {method}")

    calibrated = calibrator.predict(raw_probs) if method == "isotonic" else calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
    logger.info(f"Calibration ({method}) - Raw mean: {raw_probs.mean():.4f}, Calibrated mean: {calibrated.mean():.4f}")

    return calibrator
