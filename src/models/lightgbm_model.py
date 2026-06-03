"""LightGBM model training."""

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from loguru import logger


def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    params: dict,
    tune: bool = False,
) -> lgb.Booster:
    """Train LightGBM model with optional Optuna tuning."""

    if tune:
        logger.info("Running hyperparameter tuning...")
        params = _tune_hyperparams(X_train, y_train, X_val, y_val, params)

    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    lgb_params = {
        "objective": params.get("objective", "binary"),
        "metric": params.get("metric", ["binary_logloss", "auc"]),
        "boosting_type": params.get("boosting_type", "gbdt"),
        "num_leaves": params.get("num_leaves", 63),
        "learning_rate": params.get("learning_rate", 0.05),
        "max_depth": params.get("max_depth", 10),
        "min_child_samples": params.get("min_child_samples", 50),
        "subsample": params.get("subsample", 0.8),
        "colsample_bytree": params.get("colsample_bytree", 0.8),
        "scale_pos_weight": params.get("scale_pos_weight", 9.0),
        "verbose": params.get("verbose", -1),
    }

    model = lgb.train(
        lgb_params,
        train_data,
        num_boost_round=params.get("n_estimators", 1000),
        valid_sets=[val_data],
        callbacks=[lgb.early_stopping(params.get("early_stopping_rounds", 50))],
    )

    logger.info(f"Best iteration: {model.best_iteration}")
    return model


def _tune_hyperparams(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    base_params: dict,
) -> dict:
    """Tune hyperparameters using Optuna."""

    def objective(trial):
        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "num_leaves": trial.suggest_int("num_leaves", 31, 255),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "max_depth": trial.suggest_int("max_depth", 5, 15),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 100),
            "subsample": trial.suggest_float("subsample", 0.6, 0.95),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 0.95),
            "scale_pos_weight": base_params.get("scale_pos_weight", 9.0),
            "verbose": -1,
        }

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        model = lgb.train(
            params, train_data,
            num_boost_round=500,
            valid_sets=[val_data],
            callbacks=[lgb.early_stopping(30)],
        )

        preds = model.predict(X_val)
        from sklearn.metrics import log_loss
        return log_loss(y_val, preds)

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=base_params.get("n_trials", 100), timeout=3600)

    best = {**base_params, **study.best_params}
    logger.info(f"Best params: {study.best_params}")
    return best
