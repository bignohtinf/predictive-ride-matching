"""SageMaker inference handler / Flask app for serving predictions."""

import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from loguru import logger

from src.features.transformations import build_features

app = Flask(__name__)

# Global model objects
MODEL = None
CALIBRATOR = None
FEATURE_COLS = None


def load_model():
    """Load model artifacts from model directory."""
    global MODEL, CALIBRATOR, FEATURE_COLS

    model_dir = os.environ.get("MODEL_DIR", "/opt/ml/model")
    model_path = Path(model_dir) / "model.pkl"

    with open(model_path, "rb") as f:
        artifacts = pickle.load(f)

    MODEL = artifacts["model"]
    CALIBRATOR = artifacts.get("calibrator")
    FEATURE_COLS = artifacts["features"]
    logger.info(f"Model loaded. Features: {len(FEATURE_COLS)}")


@app.before_request
def ensure_model():
    if MODEL is None:
        load_model()


@app.route("/ping", methods=["GET"])
def ping():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200


@app.route("/invocations", methods=["POST"])
def predict():
    """Prediction endpoint."""
    try:
        data = request.get_json()
        df = pd.DataFrame(data["instances"])

        # Apply feature engineering
        df = build_features(df)

        # Ensure all required features present
        missing = [c for c in FEATURE_COLS if c not in df.columns]
        if missing:
            logger.warning(f"Missing features (using 0): {missing}")
            for c in missing:
                df[c] = 0

        X = df[FEATURE_COLS]

        # Predict
        raw_probs = MODEL.predict(X)

        # Calibrate
        if CALIBRATOR is not None:
            if hasattr(CALIBRATOR, "predict"):
                probs = CALIBRATOR.predict(raw_probs)
            else:
                probs = CALIBRATOR.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
        else:
            probs = raw_probs

        return jsonify({
            "predictions": probs.tolist(),
            "raw_scores": raw_probs.tolist(),
        })

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
