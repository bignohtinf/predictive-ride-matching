"""LightGBM classifier for CRP."""

import lightgbm as lgb

SEED = 42


def create_model(n_estimators: int = 500) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(
        n_estimators=n_estimators,
        num_leaves=31,
        learning_rate=0.05,
        max_depth=7,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=SEED,
        verbose=-1,
        n_jobs=-1,
    )
