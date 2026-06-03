"""Data and concept drift detection."""

import numpy as np
import pandas as pd
from loguru import logger


def population_stability_index(reference: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
    """Calculate PSI between reference and current distributions.

    PSI < 0.1: No significant change
    0.1 <= PSI < 0.2: Moderate change, investigate
    PSI >= 0.2: Significant change, retrain
    """
    ref_pcts, bin_edges = np.histogram(reference, bins=n_bins)
    cur_pcts, _ = np.histogram(current, bins=bin_edges)

    # Normalize to percentages
    ref_pcts = ref_pcts / len(reference) + 1e-6
    cur_pcts = cur_pcts / len(current) + 1e-6

    psi = np.sum((cur_pcts - ref_pcts) * np.log(cur_pcts / ref_pcts))
    return float(psi)


def kl_divergence(p: np.ndarray, q: np.ndarray, n_bins: int = 50) -> float:
    """KL-divergence between two distributions."""
    p_hist, bin_edges = np.histogram(p, bins=n_bins, density=True)
    q_hist, _ = np.histogram(q, bins=bin_edges, density=True)

    p_hist = p_hist + 1e-10
    q_hist = q_hist + 1e-10

    return float(np.sum(p_hist * np.log(p_hist / q_hist)))


def check_feature_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    features: list[str],
    psi_threshold: float = 0.2,
) -> dict:
    """Check all features for distribution drift."""
    results = {}
    for feat in features:
        if feat not in reference_df.columns or feat not in current_df.columns:
            continue

        psi = population_stability_index(
            reference_df[feat].dropna().values,
            current_df[feat].dropna().values,
        )

        status = "OK" if psi < 0.1 else "WARNING" if psi < psi_threshold else "CRITICAL"
        results[feat] = {"psi": round(psi, 4), "status": status}

        if status != "OK":
            logger.warning(f"Drift detected: {feat} PSI={psi:.4f} ({status})")

    return results
