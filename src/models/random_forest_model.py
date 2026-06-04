"""Random Forest classifier for CRP."""

from sklearn.ensemble import RandomForestClassifier

SEED = 42


def create_model(n_estimators: int = 672) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=8,
        min_samples_leaf=5,
        min_samples_split=50,
        max_features=0.3,
        random_state=SEED,
        n_jobs=-1,
    )
