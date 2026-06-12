import sys
from pathlib import Path
from datetime import datetime, timedelta
from feast import FeatureStore
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FEAST_REPO = PROJECT_ROOT / "src" / "features" / "feature_store"


def materialize_to_online_store():
    store = FeatureStore(repo_path=str(FEAST_REPO))

    end_date = datetime.now().astimezone()
    start_date = end_date - timedelta(days=90)

    print(f"Materializing features to Redis online store...")
    print(f"  Period: {start_date.date()} → {end_date.date()}")

    store.materialize(
        start_date=start_date,
        end_date=end_date,
    )
    print("Materialization complete.")


def query_online_features(order_ids: list[str]):
    store = FeatureStore(repo_path=str(FEAST_REPO))

    entity_rows = [{"order_id": oid} for oid in order_ids]

    feature_refs = [
        "order_raw_features:user_waiting_time_seconds",
        "order_raw_features:num_drivers",
        "order_raw_features:num_orders",
        "order_raw_features:eta_avg",
        "order_raw_features:distance",
        "order_raw_features:total_fee",
        "order_raw_features:hour_of_day",
        "order_raw_features:rush_hour",
    ]

    print(f"Querying online store for {len(order_ids)} orders...")
    online_features = store.get_online_features(
        features=feature_refs,
        entity_rows=entity_rows,
    ).to_dict()

    result = pd.DataFrame(online_features)
    print(result.to_string(index=False))
    return result


def demo_online_serving():
    raw_path = FEAST_REPO / "data" / "raw_features.parquet"
    if not raw_path.exists():
        print("No feast data found. Run prepare_feast_data first.")
        return

    df = pd.read_parquet(raw_path)
    sample_orders = df["order_id"].head(5).tolist()

    print("=" * 60)
    print("ONLINE FEATURE SERVING DEMO (mock)")
    print("=" * 60)
    print(f"\nSample orders: {sample_orders}")

    # Simulate online store lookup
    features_for_orders = df[df["order_id"].isin(sample_orders)][[
        "order_id", "user_waiting_time_seconds", "num_drivers",
        "num_orders", "eta_avg", "distance", "total_fee",
        "hour_of_day", "rush_hour",
    ]]
    print(f"\nFeatures (from mock online store):")
    print(features_for_orders.to_string(index=False))

    # Show what inference would look like
    print(f"\n→ These features would be passed to the model for real-time prediction.")
    print(f"  Latency: <5ms (Redis) vs ~100ms (offline store)")
    return features_for_orders


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["materialize", "query", "demo"], default="demo", nargs="?")
    parser.add_argument("--order-id", nargs="+", default=None)
    args = parser.parse_args()

    if args.action == "materialize":
        materialize_to_online_store()
    elif args.action == "query":
        order_ids = args.order_id or ["0", "1", "2"]
        query_online_features(order_ids)
    else:
        demo_online_serving()
