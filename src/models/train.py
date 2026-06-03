"""Model training orchestrator."""

import argparse
import pickle
from pathlib import Path

import pandas as pd
import yaml
from loguru import logger

from src.data.preprocessing import preprocess_pipeline, temporal_train_test_split
from src.features.transformations import build_features
from src.models.lightgbm_model import train_lightgbm
from src.models.calibration import calibrate_model
from src.evaluation.metrics import evaluate_model


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_feature_columns(config_path: str = "configs/feature_config.yaml") -> list[str]:
    """Get list of safe feature columns from config."""
    with open(config_path) as f:
        feature_config = yaml.safe_load(f)

    features = []
    for category in feature_config["features"]["safe_features"].values():
        features.extend(category)
    return features


def main(config_path: str, tune: bool = False):
    config = load_config(config_path)
    feature_config = load_config("configs/feature_config.yaml")

    # Load data
    logger.info("Loading data...")
    df = pd.read_csv("data/processed/ride_data.csv")

    # Preprocess
    df = preprocess_pipeline(df, feature_config["features"]["preprocessing"])

    # Feature engineering
    df = build_features(df)

    # Split (temporal)
    train_df, val_df, test_df = temporal_train_test_split(
        df, time_col="hour_of_day",  # Replace with actual timestamp in production
        train_ratio=1 - config["training"]["test_size"] - config["training"]["val_size"],
        val_ratio=config["training"]["val_size"],
    )

    # Get feature columns
    feature_cols = get_feature_columns()
    # Add derived features
    derived = ["supply_demand_ratio", "batch_competition", "hour_sin", "hour_cos",
               "eta_to_distance_ratio", "fee_per_km", "high_wait_flag"]
    feature_cols = [c for c in feature_cols + derived if c in train_df.columns]
    target = "is_completed"

    X_train, y_train = train_df[feature_cols], train_df[target]
    X_val, y_val = val_df[feature_cols], val_df[target]
    X_test, y_test = test_df[feature_cols], test_df[target]

    # Train
    logger.info(f"Training with {len(feature_cols)} features...")
    model = train_lightgbm(
        X_train, y_train, X_val, y_val,
        params=config["model"]["lightgbm"],
        tune=tune,
    )

    # Calibrate
    logger.info("Calibrating model...")
    calibrator = calibrate_model(model, X_val, y_val, method=config["model"]["calibration"]["method"])

    # Evaluate
    logger.info("Evaluating on test set...")
    metrics = evaluate_model(model, X_test, y_test, calibrator=calibrator)
    logger.info(f"Test metrics: {metrics}")

    # Check thresholds
    thresholds = config["evaluation"]["thresholds"]
    passed = (
        metrics["auc_roc"] >= thresholds["auc_roc_min"]
        and metrics["log_loss"] <= thresholds["log_loss_max"]
    )
    logger.info(f"Threshold check: {'PASSED' if passed else 'FAILED'}")

    # Save
    output_dir = Path("data/models")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "model.pkl", "wb") as f:
        pickle.dump({"model": model, "calibrator": calibrator, "features": feature_cols, "metrics": metrics}, f)
    logger.info(f"Model saved to {output_dir / 'model.pkl'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/model_config.yaml")
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()
    main(args.config, args.tune)
