"""Stacking ensemble: LightGBM + XGBoost + RF → LogisticRegression meta-learner."""

from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression

from src.models.lightgbm_model import create_model as create_lgb
from src.models.xgboost_model import create_model as create_xgb
from src.models.random_forest_model import create_model as create_rf

SEED = 42


def create_stacking_model(n_estimators: int = 500) -> StackingClassifier:
    return StackingClassifier(
        estimators=[
            ("lgb", create_lgb(n_estimators)),
            ("xgb", create_xgb(n_estimators)),
            ("rf", create_rf(n_estimators)),
        ],
        final_estimator=LogisticRegression(max_iter=1000, random_state=SEED),
        cv=5,
        stack_method="predict_proba",
        passthrough=False,
        n_jobs=-1,
    )
