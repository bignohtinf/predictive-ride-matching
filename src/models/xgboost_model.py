"""XGBoost classifier for CRP."""

import xgboost as xgb

SEED = 42


def create_model(n_estimators: int = 500) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        eval_metric="logloss",
        random_state=SEED,
        n_jobs=-1,
    )
