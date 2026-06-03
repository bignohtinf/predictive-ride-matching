import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd


def generate_synthetic_data(num_rows: int = 1000, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)

    order_ids = [f"order_{i}" for i in range(1, num_rows + 1)]
    batch_ids = [f"batch_{np.random.randint(1, int(num_rows * 0.8) + 1)}" for _ in range(num_rows)]
    driver_ids = [f"driver_{np.random.randint(1, int(num_rows * 0.5) + 1)}" for _ in range(num_rows)]

    num_drivers = np.random.randint(1, 150, size=num_rows)
    num_orders = np.random.randint(1, 100, size=num_rows)

    eta_avg = np.random.uniform(60, 1800, size=num_rows)
    eta_std = np.random.uniform(5, 300, size=num_rows)
    eta_min = np.clip(eta_avg - np.random.uniform(10, 60, size=num_rows), 10, None)
    eta_inv1 = 1 / (eta_avg + 1)
    eta_inv10 = 1 / (eta_avg + 10)
    eta_inv100 = 1 / (eta_avg + 100)

    eda_avg = np.random.uniform(0.5, 15.0, size=num_rows)
    eda_std = np.random.uniform(0.1, 2.0, size=num_rows)
    eda_min = np.clip(eda_avg - np.random.uniform(0.1, 1.0, size=num_rows), 0.1, None)
    eda_inv1 = 1 / (eda_avg + 1)
    eda_inv10 = 1 / (eda_avg + 10)
    eda_inv100 = 1 / (eda_avg + 100)

    # Realistic hour distribution: peak 8-11h (morning) and 14-22h (afternoon/evening)
    # Very sparse 0-5h (late night), low 6-7h and 23h
    hour_weights = np.array([
        1, 1, 1, 1, 1, 2,   # 0-5h: rất khuya / đêm khuya
        4, 5,               # 6-7h: sáng sớm
        8, 9, 9, 8,         # 8-11h: cao điểm sáng
        5, 5,               # 12-13h: trưa
        7, 8, 8, 8, 8, 8, 7, 7, 6,  # 14-22h: cao điểm chiều/tối
        3,                  # 23h: đêm muộn
    ], dtype=float)
    hour_weights /= hour_weights.sum()
    hour_of_day = np.random.choice(24, size=num_rows, p=hour_weights)
    minute_of_hour = np.random.randint(0, 60, size=num_rows)
    rush_hour = np.where(
        (hour_of_day >= 7) & (hour_of_day <= 9) | (hour_of_day >= 16) & (hour_of_day <= 19), 1, 0
    )

    # 1=xe máy, 2=giao hàng, 3=ô tô — xe máy+giao hàng gấp ~3-4x ô tô
    travel_mode = np.random.choice([1, 2, 3], size=num_rows, p=[0.42, 0.38, 0.20])
    user_waiting_time_seconds = np.random.uniform(30, 900, size=num_rows)
    distance = np.clip(eda_avg + np.random.normal(0, 0.5, size=num_rows), 0.1, None)

    # Giá cước theo loại phương tiện
    base_rate = np.where(travel_mode == 1, 12000,          # xe máy
               np.where(travel_mode == 2, 15000, 35000))   # giao hàng / ô tô
    price_per_km = np.where(travel_mode == 1, 4000,
                   np.where(travel_mode == 2, 5000, 11000))
    surge_multiplier = np.where(rush_hour == 1, np.random.uniform(1.2, 1.5, size=num_rows), 1.0)
    total_fee_raw = (base_rate + distance * price_per_km) * surge_multiplier
    # Áp sàn giá tối thiểu: xe máy/giao hàng >= 20k, ô tô >= 50k
    fee_floor = np.where(travel_mode == 3, 50000, 20000)
    total_fee = np.round(np.maximum(total_fee_raw, fee_floor), -3)
    total_pay = np.round(total_fee * np.random.uniform(0.7, 1.0, size=num_rows), -3)

    est_time_arrival = eta_avg + np.random.normal(0, 60, size=num_rows)
    est_distance_arrival = eda_avg + np.random.normal(0, 0.2, size=num_rows)
    estimate_dropoff_time = int(time.time()) + (est_time_arrival * 1000)

    is_completed = np.random.choice([1, 0], p=[0.9, 0.1], size=num_rows)

    data = {
        "order_id": order_ids,
        "matching_batch_id": batch_ids,
        "driver_id": driver_ids,
        "num_drivers": num_drivers,
        "num_orders": num_orders,
        "eta_avg": eta_avg,
        "eta_std": eta_std,
        "eta_min": eta_min,
        "eta_inv1": eta_inv1,
        "eta_inv10": eta_inv10,
        "eta_inv100": eta_inv100,
        "eda_avg": eda_avg,
        "eda_std": eda_std,
        "eda_min": eda_min,
        "eda_inv1": eda_inv1,
        "eda_inv10": eda_inv10,
        "eda_inv100": eda_inv100,
        "hour_of_day": hour_of_day,
        "minute_of_hour": minute_of_hour,
        "rush_hour": rush_hour,
        "travel_mode": travel_mode,
        "user_waiting_time_seconds": user_waiting_time_seconds,
        "distance": distance,
        "total_fee": total_fee,
        "total_pay": total_pay,
        "est_time_arrival": est_time_arrival,
        "est_distance_arrival": est_distance_arrival,
        "estimate_dropoff_time": estimate_dropoff_time,
        "is_completed": is_completed,
    }

    return pd.DataFrame(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-rows", type=int, default=1500000)
    parser.add_argument("--output", default="data/raw/synthetic_ride_data.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df = generate_synthetic_data(args.num_rows, args.seed)
    df.to_csv(args.output, index=False)
    print(f"Generated {len(df)} rows -> {args.output}")
