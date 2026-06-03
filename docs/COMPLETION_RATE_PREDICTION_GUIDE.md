# Completion Rate Prediction (CRP) trong Ride-Hailing Matching

## Mục lục

1. [Bối cảnh: Bài toán Matching](#1-bối-cảnh-bài-toán-matching)
2. [CRP trong Matching Pipeline](#2-crp-trong-matching-pipeline)
3. [Feature Engineering theo Domain Signal](#3-feature-engineering-theo-domain-signal)
4. [Data Leakage — Rủi ro lớn nhất](#4-data-leakage--rủi-ro-lớn-nhất)
5. [Modeling Strategy](#5-modeling-strategy)
6. [Evaluation — Đo đúng thứ cần đo](#6-evaluation--đo-đúng-thứ-cần-đo)
7. [Serving trong Matching Pipeline](#7-serving-trong-matching-pipeline)
8. [Các biến thể nâng cao: Ride-pooling & Chaining](#8-các-biến-thể-nâng-cao-ride-pooling--chaining)
9. [Monitoring & Feedback Loop](#9-monitoring--feedback-loop)
10. [Roadmap triển khai](#10-roadmap-triển-khai)

---

## 1. Bối cảnh: Bài toán Matching

### 1.1 Greedy vs Batch Matching

Matching trong ride-hailing đã tiến hóa qua 2 giai đoạn:

**Greedy Matching (cổ điển):** Khi khách đặt xe, hệ thống quét bán kính xung quanh, tìm tài xế gần nhất, phát cuốc ngay. Vấn đề: tối ưu cục bộ (local optima). Khách A lấy mất tài xế gần nhất của Khách B xuất hiện 1 giây sau.

**Batch Matching (hiện đại):** Hệ thống gom tất cả riders và drivers trong khu vực vào một "lô" (batch) mỗi 2-5 giây. Xây dựng bipartite graph, giải bài toán tối ưu toàn cục (global optimization) để tìm tập hợp cặp ghép tối ưu nhất.

### 1.2 Objective Function thực tế

Hệ thống production không chỉ minimize ETA. Hàm mục tiêu thực sự là tổ hợp đa mục tiêu:

- **Minimize tổng ETA**: Giảm thời gian đón
- **Maximize Completion Rate**: Cuốc xe thực sự được hoàn thành
- **Maximize Driver Utilization**: Giảm idle time
- **Maximize Platform Revenue/GMV**: Tối ưu doanh thu

Khi đưa CRP vào, objective chuyển từ:

```
max(Số cặp ghép)  hoặc  min(Tổng ETA)
```

Thành:

```
max Σ (Giá trị cuốc xe × Xác suất hoàn thành CRP)
```

Đây là bước chuyển từ "khớp lệnh mù quáng" sang "khớp lệnh thông minh" — ra quyết định dưới điều kiện không chắc chắn (Decision Making under Uncertainty).

---

## 2. CRP trong Matching Pipeline

### 2.1 Vai trò của CRP

CRP đóng vai trò **bộ lọc rủi ro / trọng số** cho matching optimizer. Nếu Matching là bộ não tìm mọi phương án ghép cặp, thì CRP giúp bộ não đó chọn phương án có khả năng thành công cao nhất.

### 2.2 Pipeline 3 bước trong mỗi Batch Cycle (2-5 giây)

**Bước 1 — Candidate Generation:**
Thuật toán tìm kiếm không gian (Uber H3, Google S2) quét và tạo ma trận các cặp ghép khả thi. Ví dụ: Khách A có thể ghép với Tài xế X hoặc Y.

**Bước 2 — CRP Scoring:**
Toàn bộ cặp ứng viên được đẩy qua model CRP:

| Cặp | ETA | Context | CRP Score |
|-----|-----|---------|-----------|
| Khách A — Tài xế X | 3 phút | Tài xế X hay hủy giờ cao điểm, đường thắt nút | **45%** |
| Khách A — Tài xế Y | 5 phút | Tài xế Y đang hướng thẳng về, đường thông | **92%** |

**Bước 3 — Global Optimization:**
Thuật toán ILP/Hungarian nhận ma trận CRP score làm input. Thay vì chọn Tài xế X (gần hơn, greedy), hệ thống chọn Tài xế Y vì Expected Value cao hơn:

```
EV(A-X) = Giá trị cuốc × 0.45 = thấp
EV(A-Y) = Giá trị cuốc × 0.92 = cao  ← chọn
```

### 2.3 Ràng buộc thời gian

CRP model phải inference trong **< 10-20ms per pair** vì:
- Batch cycle = 2-5 giây
- Mỗi batch có thể có hàng nghìn cặp ứng viên
- Còn phải chừa thời gian cho optimization solver

---

## 3. Feature Engineering theo Domain Signal

Đây là phần QUAN TRỌNG NHẤT. Features phải capture được **lý do thực sự** khiến cuốc xe bị hủy, chia thành 6 nhóm signal:

### 3.1 Driver Behavioral Signal — "Tài xế này có đáng tin không?"

Đây là nhóm features mạnh nhất vì hành vi tài xế là yếu tố dự đoán hủy cuốc số 1.

| Feature | Ý nghĩa | Cách tính |
|---------|---------|-----------|
| `driver_completion_rate_7d` | Tỷ lệ hoàn thành 7 ngày gần nhất | Rolling mean trên completed orders |
| `driver_completion_rate_30d` | Tỷ lệ hoàn thành 30 ngày | Smoother, ít noise hơn 7d |
| `driver_cancel_streak` | Số cuốc liên tiếp tài xế hủy gần nhất | Reset khi hoàn thành 1 cuốc |
| `driver_cancel_rate_rush_hour` | Tỷ lệ hủy riêng giờ cao điểm | Nhiều tài xế chỉ hủy khi kẹt xe |
| `driver_acceptance_rate` | Tỷ lệ chấp nhận cuốc (không bỏ qua) | Accepted / offered trong 7d |
| `driver_avg_eta_tolerance` | Ngưỡng ETA trung bình tài xế chấp nhận | Median ETA của các cuốc đã nhận |
| `driver_total_trips` | Tổng số chuyến đã hoàn thành | Proxy cho kinh nghiệm |
| `driver_active_hours_today` | Số giờ đã chạy trong ngày | Proxy cho mệt mỏi |
| `driver_trips_today` | Số cuốc đã hoàn thành hôm nay | Kết hợp với active_hours → fatigue |
| `driver_last_cancel_minutes_ago` | Thời gian từ lần hủy gần nhất | Gần = high risk |
| `driver_earnings_today` | Thu nhập hiện tại trong ngày | Ảnh hưởng motivation |
| `driver_rating` | Rating trung bình | Low rating → unstable behavior |

**Insight quan trọng:** `driver_cancel_rate_rush_hour` thường có predictive power cao hơn `driver_completion_rate_30d` tổng quát, vì pattern hủy cuốc thường cluster theo context cụ thể (giờ, khu vực, loại xe).

### 3.2 Rider Behavioral Signal — "Khách này có đủ kiên nhẫn không?"

| Feature | Ý nghĩa | Cách tính |
|---------|---------|-----------|
| `rider_cancel_rate_history` | Tỷ lệ khách hủy trong lịch sử | Tổng cancel / tổng order |
| `rider_avg_wait_tolerance` | Thời gian chờ trung bình trước khi hủy | Median wait time của các lần hủy |
| `rider_total_trips` | Số chuyến đã đi | Khách quen vs khách mới |
| `rider_is_new_user` | Khách mới (< 3 chuyến) | Khách mới có cancel rate cao hơn |
| `rider_current_wait_seconds` | Thời gian khách đã chờ từ lúc đặt | Càng lâu → càng mất kiên nhẫn |
| `rider_wait_to_tolerance_ratio` | `current_wait / avg_wait_tolerance` | > 1.0 = nguy hiểm |
| `rider_surge_acceptance` | Khách có chấp nhận surge pricing không | Chấp nhận surge → committed hơn |

**Insight:** `rider_wait_to_tolerance_ratio` là feature cực mạnh. Khi ratio vượt 1.0, xác suất hủy tăng đột biến (non-linear). Nên tạo thêm binary flag `rider_patience_exceeded = (ratio > 1.0)`.

### 3.3 Spatial & Routing Signal — "Đường đi có khả thi không?"

Đây là nhóm features giải thích sự khác biệt giữa ETA lý thuyết và khả năng thực tế.

| Feature | Ý nghĩa | Cách tính |
|---------|---------|-----------|
| `eta_avg` | ETA trung bình (giây) | Từ routing engine |
| `eta_std` | Độ lệch chuẩn ETA | Cao = tuyến đường không chắc chắn |
| `eta_min` | ETA tốt nhất có thể | Lower bound |
| `eda_avg` | Khoảng cách đón (km) | Euclidean hoặc road distance |
| `eta_confidence` | `eta_std / eta_avg` | Coefficient of variation — routing uncertainty |
| `route_complexity` | Số lượt rẽ / U-turn trên tuyến đón | Đường phức tạp → dễ lạc → dễ hủy |
| `is_opposite_direction` | Tài xế đang đi ngược chiều pickup | Binary flag — signal rất mạnh |
| `road_segment_congestion` | Mức độ kẹt xe trên tuyến đón | Real-time traffic data |
| `pickup_area_accessibility` | Độ dễ tiếp cận điểm đón | Hẻm nhỏ, ngõ cụt, tòa nhà = khó |
| `h3_hex_completion_rate` | Tỷ lệ hoàn thành theo ô H3 hexagon | Completion rate trung bình tại khu vực |
| `h3_hex_demand_density` | Mật độ nhu cầu tại ô H3 | High demand = nhiều lựa chọn cho cả 2 bên |
| `dropoff_distance` | Khoảng cách toàn chuyến (pickup → dropoff) | Cuốc ngắn quá → tài xế không muốn nhận |
| `detour_ratio` | ETA thực / ETA đường thẳng | > 1.5 = đường vòng nhiều |

**Inverse transforms cho ETA/EDA:**
Các biến `eta_inv1`, `eta_inv10`, `eta_inv100` (= 1/(eta + k)) giúp model capture mối quan hệ phi tuyến: ETA từ 2→5 phút ảnh hưởng completion rate nhiều hơn ETA từ 20→23 phút. Inverse transform "kéo giãn" vùng giá trị nhỏ (quan trọng) và "nén" vùng giá trị lớn (ít quan trọng).

### 3.4 Supply-Demand Signal — "Thị trường đang như thế nào?"

| Feature | Ý nghĩa | Cách tính |
|---------|---------|-----------|
| `num_drivers` | Số tài xế trống trong khu vực | Real-time count |
| `num_orders` | Số đơn chờ ghép trong batch | Real-time count |
| `supply_demand_ratio` | `num_drivers / num_orders` | < 1.0 = thiếu supply |
| `surge_multiplier` | Hệ số surge pricing hiện tại | High surge → driver motivated, rider impatient |
| `surge_level` | Bucket: none/low/medium/high | Categorical version |
| `competing_orders_same_area` | Số đơn cạnh tranh cùng khu vực | Nhiều đơn → tài xế có nhiều lựa chọn |

**Insight:** Khi `supply_demand_ratio < 0.5` (thiếu tài xế nghiêm trọng), tài xế có quyền "chọn cuốc ngon" → cancel rate của cuốc ngắn/giá thấp tăng mạnh. Feature interaction: `supply_demand_ratio × dropoff_distance` rất có giá trị.

### 3.5 Match-Specific Signal — "Cặp ghép này có hợp lý không?"

Đây là nhóm features chỉ tồn tại tại thời điểm matching, mô tả chất lượng của cặp (rider, driver) cụ thể.

| Feature | Ý nghĩa | Cách tính |
|---------|---------|-----------|
| `driver_heading_alignment` | Góc giữa hướng di chuyển tài xế và hướng đến pickup | cos(angle) — 1.0 = cùng chiều, -1.0 = ngược chiều |
| `fee_per_km` | Giá trên mỗi km | `total_fee / distance` |
| `price_vs_area_avg` | Giá cuốc so với trung bình khu vực | `total_fee / avg_fee_same_area` |
| `eta_vs_driver_tolerance` | ETA so với ngưỡng chịu đựng của tài xế | `eta / driver_avg_eta_tolerance` |
| `is_short_trip` | Cuốc ngắn (< 2km) | Tài xế hay reject cuốc ngắn giờ cao điểm |
| `trip_value_score` | Giá trị cuốc = fee × completion_prob × distance efficiency | Composite score |
| `total_fee` | Tổng phí cuốc xe | Base + distance × rate × surge |
| `travel_mode` | Loại dịch vụ (bike/car/delivery) | Categorical |

### 3.6 Temporal Signal — "Thời điểm nào?"

| Feature | Ý nghĩa | Cách tính |
|---------|---------|-----------|
| `hour_of_day` | Giờ trong ngày (0-23) | Trực tiếp |
| `hour_sin`, `hour_cos` | Cyclical encoding | sin/cos(2π × hour/24) |
| `minute_of_hour` | Phút trong giờ | Granularity cao hơn |
| `rush_hour` | Giờ cao điểm (7-9, 16-19) | Binary flag |
| `day_of_week` | Ngày trong tuần | 0=Mon, 6=Sun |
| `is_weekend` | Cuối tuần | Pattern hủy khác hẳn ngày thường |
| `is_rain_hour` | Giờ đang mưa | Weather API — mưa = tăng demand, tăng cancel |
| `minutes_since_midnight` | Phút từ 0h | Continuous alternative cho hour |

---

## 4. Data Leakage — Rủi ro lớn nhất

### 4.1 Nguyên tắc vàng

> **Chỉ được dùng features có sẵn TẠI THỜI ĐIỂM MATCHING (trước khi cuốc xe bắt đầu).**

Mọi thông tin chỉ biết SAU KHI cuốc xe diễn ra hoặc hoàn thành đều là leakage.

### 4.2 Bảng phân loại features

| Feature | Available at matching? | Verdict |
|---------|----------------------|---------|
| `eta_avg`, `eta_std`, `eta_min` | Có — routing engine tính trước | ✅ Safe |
| `eda_avg`, `eda_std`, `eda_min` | Có — khoảng cách tính trước | ✅ Safe |
| `num_drivers`, `num_orders` | Có — biết ngay lúc batching | ✅ Safe |
| `total_fee` | Có — tính từ distance + surge | ✅ Safe |
| `driver_completion_rate_7d` | Có — precomputed batch feature | ✅ Safe |
| `est_time_arrival` | **Không** — thời gian đón thực tế, chỉ biết sau | ❌ Leakage |
| `est_distance_arrival` | **Không** — khoảng cách đón thực tế | ❌ Leakage |
| `estimate_dropoff_time` | **Không** — derived từ est_time_arrival | ❌ Leakage |
| `total_pay` | **Có thể không** — nếu chỉ tính khi completed | ⚠️ Kiểm tra logic |
| `is_completed` | Target variable | 🎯 Target |

### 4.3 Temporal Leakage

Random split trên data có timestamp = leakage ngầm. Model "nhìn thấy" pattern tương lai.

**Bắt buộc dùng temporal split:**
- Train: Tháng 1-3
- Validation: Tháng 4
- Test: Tháng 5
- Không shuffle, không stratified random

### 4.4 Feature Leakage từ Aggregation

Cẩn thận khi tính `driver_completion_rate_7d`: phải tính trên data TRƯỚC thời điểm matching của record hiện tại, không được include chính record đó hoặc records tương lai. Dùng **point-in-time correct joins**.

---

## 5. Modeling Strategy

### 5.1 Tại sao Gradient Boosting, không phải Deep Learning?

Với bài toán CRP trong matching pipeline, LightGBM/XGBoost là lựa chọn tối ưu vì:

- **Latency**: Inference < 1ms/sample (DNN có thể 5-10ms)
- **Tabular data**: GBDT vẫn dominant trên tabular features
- **Interpretability**: Feature importance giúp debug tại sao cuốc bị predict thấp
- **Data size**: GBDT hoạt động tốt với 100K-10M samples. Với ~7.6M records hiện tại, đây là sweet spot cho GBDT
- **Calibration**: GBDT output dễ calibrate hơn

Với 7.6M records, DNN trở nên khả thi nhưng chưa cần thiết trừ khi muốn: embedding cho high-cardinality IDs (driver_id, area_id, h3_hex), capture sequential patterns (chuỗi hành vi driver trong ngày), hoặc multi-task learning (predict cả driver-cancel và rider-cancel cùng lúc). Nếu thử DNN, bắt đầu với architecture đơn giản (2-3 hidden layers + entity embeddings) và benchmark so với LightGBM.

### 5.2 Model Configuration

```yaml
lightgbm:
  objective: binary
  metric: [binary_logloss, auc]
  num_leaves: 63
  learning_rate: 0.05
  max_depth: 10
  min_child_samples: 50
  subsample: 0.8
  colsample_bytree: 0.8
  scale_pos_weight: 9.0  # 90/10 imbalance
  early_stopping_rounds: 50
```

### 5.3 Class Imbalance (90/10)

Dataset có ~90% completed, ~10% cancelled. Cách xử lý:

- `scale_pos_weight = 9.0` trong LightGBM (nặng weight cho minority class)
- Focal Loss nếu cần focus vào hard-to-classify samples
- **KHÔNG dùng accuracy** — 90% accuracy = predict tất cả là completed
- **KHÔNG oversample (SMOTE)** cho tree-based models — không cần thiết, `scale_pos_weight` đủ

### 5.4 Probability Calibration — Bắt buộc

CRP output phải là **xác suất thực** (well-calibrated) vì matching optimizer so sánh score giữa các cặp. Nếu model predict 70% nhưng thực tế chỉ 50% hoàn thành → optimizer ra quyết định sai.

- **Isotonic Regression**: Flexible, non-parametric, cần ~5K+ validation samples
- **Platt Scaling**: Simple logistic regression trên raw output, ít data hơn
- **Reliability diagram**: Visualize calibration quality
- **Target: ECE (Expected Calibration Error) < 0.05**

---

## 6. Evaluation — Đo đúng thứ cần đo

### 6.1 Offline Metrics

| Metric | Tại sao cần | Target |
|--------|-------------|--------|
| **AUC-ROC** | Khả năng phân biệt completed vs cancelled, threshold-independent | > 0.80 |
| **AUC-PR** | Quan trọng hơn ROC khi imbalanced — focus vào minority (cancelled) | > 0.50 cho class 0 |
| **Log Loss** | Đo chất lượng probability estimation — quan trọng nhất cho ranking | < 0.25 |
| **ECE** | Calibration quality — probability có đáng tin không | < 0.05 |
| **Precision@Bottom-K** | Trong top-K dự đoán thấp nhất, bao nhiêu % thực sự cancelled | > 0.30 |

### 6.2 Tại sao Log Loss quan trọng hơn AUC cho CRP?

AUC chỉ đo ranking ability (thứ tự). Nhưng matching optimizer cần **giá trị tuyệt đối** của probability để tính Expected Value. Một model có AUC cao nhưng calibration tệ (predict 80% cho mọi sample) sẽ vô dụng cho matching.

### 6.3 Online Metrics (A/B Test)

Khi deploy CRP vào matching pipeline, đo impact thực tế:

- **Overall Completion Rate**: Tăng bao nhiêu % so với matching không có CRP?
- **GMV**: Tổng doanh thu tăng do ít cuốc cancelled?
- **Average Rider Wait Time**: Không được tăng đáng kể (trade-off)
- **Driver Utilization**: Tài xế có ít idle time hơn không?
- **Cancellation Distribution**: Cancel rate giảm đều hay chỉ giảm ở một segment?

---

## 7. Serving trong Matching Pipeline

### 7.1 Latency Budget

```
Batch cycle: 2-5 giây
├── Candidate Generation (H3 spatial search): ~200ms
├── CRP Scoring (1000-5000 pairs):            ~500ms  ← phải nằm trong đây
├── Optimization Solver (ILP/Hungarian):       ~1000ms
└── Buffer:                                    ~300ms
```

CRP phải predict 1000-5000 pairs trong 500ms → **< 0.1ms per pair** (batch inference).

### 7.2 Feature Serving Architecture

```
Batch Features (precomputed):
  driver_completion_rate_7d     ─┐
  driver_cancel_streak          ─┤
  rider_cancel_rate_history     ─┤── Redis/DynamoDB (< 1ms lookup)
  h3_hex_completion_rate        ─┤
  area_avg_eta                  ─┘

Real-time Features (computed inline):
  eta_avg, eda_avg              ─┐
  num_drivers, num_orders       ─┤── Từ matching context (đã có sẵn)
  supply_demand_ratio           ─┤
  driver_heading_alignment      ─┤
  surge_multiplier              ─┘
```

### 7.3 Fallback Strategy

Khi CRP model hoặc feature store gặp sự cố:
- **Feature store down**: Dùng default values (population mean) cho batch features
- **Model timeout**: Fallback về simple rule: `score = 1.0 - (eta/max_eta) × 0.3`
- **Full outage**: Matching chạy không có CRP score (pure ETA-based matching)

---

## 8. Các biến thể nâng cao: Ride-pooling & Chaining

### 8.0 Điều kiện tiên quyết: Driver Opt-in

**Cả ride-pooling và chaining đều phụ thuộc hoàn toàn vào tài xế bật tính năng.** Nếu tài xế không opt-in, hệ thống không được phép ghép chuyến hoặc phát cuốc cuốn chiếu, và do đó không có data để train CRP cho 2 biến thể này.

Hệ quả cho modeling:

- **Data availability**: Chỉ có data từ tài xế đã bật tính năng → selection bias. Tài xế bật ride-pooling/chaining thường là tài xế chuyên nghiệp hơn, completion rate baseline đã cao sẵn. Model train trên data này sẽ biased nếu áp dụng cho population chung.
- **Feature bắt buộc**: `driver_pooling_enabled` (binary), `driver_chaining_enabled` (binary) — phải có trong feature set. Nếu = 0 thì CRP cho pooling/chaining không applicable.
- **Separate models hoặc conditional logic**: Có thể cần model riêng cho pooling/chaining thay vì 1 model chung, vì population và feature distribution khác biệt đáng kể so với matching thông thường.
- **Cold start**: Khi tài xế mới bật tính năng, chưa có historical data cho pooling/chaining → dùng general CRP score + default priors.

### 8.1 Ride-pooling (Ghép chuyến)

Khi hệ thống định ghép Khách B vào chuyến đang chở Khách A, CRP cần trả lời: **"Nếu bắt Khách A đợi thêm 4 phút để đón Khách B, xác suất Khách A hủy là bao nhiêu?"**

Lưu ý: Chỉ đánh giá khi `driver_pooling_enabled = 1`.

Features bổ sung cho ride-pooling:

| Feature | Ý nghĩa |
|---------|---------|
| `detour_time_existing_rider` | Thời gian đi vòng thêm cho khách đang trên xe |
| `delay_ratio_existing_rider` | `detour_time / original_trip_time` — > 0.3 thường là ngưỡng nguy hiểm |
| `existing_rider_wait_so_far` | Khách A đã chờ bao lâu rồi? Càng lâu → càng mất kiên nhẫn |
| `seats_remaining` | Số ghế trống |
| `existing_rider_cancel_history` | Khách A có hay hủy ghép chuyến không? |
| `route_overlap_ratio` | Tỷ lệ trùng lộ trình giữa 2 khách |

**Quy tắc:** Nếu `CRP(Khách A hủy | ghép Khách B) < 70%`, hệ thống hủy bỏ ý định ghép và tìm tài xế riêng cho Khách B.

### 8.2 Chaining / Dispatch Ahead (Cuốc cuốn chiếu)

Phát cuốc mới cho tài xế khi họ sắp trả khách cũ. Chỉ áp dụng khi `driver_chaining_enabled = 1`. CRP cần đánh giá 2 rủi ro:

**Rủi ro 1 — Tài xế không muốn nhận thêm:**

| Feature | Ý nghĩa |
|---------|---------|
| `driver_active_hours_today` | Mệt mỏi? |
| `driver_trips_today` | Đã chạy nhiều chưa? |
| `driver_earnings_today` | Đã đủ target thu nhập? |
| `time_until_current_dropoff` | Bao lâu nữa trả khách cũ? |
| `driver_chain_acceptance_rate` | Tỷ lệ chấp nhận cuốc chaining lịch sử |

**Rủi ro 2 — Khách mới mất kiên nhẫn:**

| Feature | Ý nghĩa |
|---------|---------|
| `estimated_wait_for_new_rider` | Thời gian khách mới phải đợi (= thời gian trả khách cũ + ETA đến pickup mới) |
| `new_rider_wait_tolerance` | Ngưỡng chịu đựng của khách mới |
| `wait_to_tolerance_ratio` | Ratio > 1.0 = nguy hiểm |

---

## 9. Monitoring & Feedback Loop

### 9.1 Drift Detection

| Monitor | Method | Alert Threshold |
|---------|--------|-----------------|
| **Data Drift** | PSI trên input features | PSI > 0.2 = retrain |
| **Concept Drift** | AUC trên labeled data (delayed) | AUC drop > 0.03 |
| **Prediction Drift** | KL-divergence trên P(completed) distribution | KL > 0.1 |
| **Calibration Drift** | ECE trên rolling window | ECE > 0.08 |
| **Business KPI** | Actual completion rate vs predicted | Gap > 5% sustained 2h |

### 9.2 Label Delay

Completion label (is_completed) chỉ biết SAU KHI cuốc xe kết thúc (có thể 30 phút - 2 giờ sau matching). Monitoring concept drift cần account for delay này — không thể real-time.

### 9.3 Feedback Loop — Cẩn thận!

Khi CRP được deploy, nó THAY ĐỔI distribution của data tương lai:

- CRP filter bỏ các cặp ghép rủi ro cao → completion rate tăng → model thấy ít negative samples hơn → model trở nên "lạc quan" hơn → filter ít đi → completion rate giảm lại

**Giải pháp: Exploration budget.** 5-10% matching decisions được làm ngẫu nhiên (không dùng CRP), để thu thập unbiased data cho retraining. Tương tự epsilon-greedy trong Reinforcement Learning.

### 9.4 Retraining Strategy

- **Frequency**: Weekly (hoặc khi drift alert trigger)
- **Data window**: Rolling 30 ngày gần nhất
- **Champion-Challenger**: Model mới phải beat model cũ trên test set + shadow deployment trước khi promote
- **Canary rollout**: 5% → 25% → 50% → 100% traffic

---

## 10. Roadmap triển khai

| Phase | Tasks | Duration |
|-------|-------|----------|
| **Phase 1** | EDA, data pipeline, baseline model (LogReg chỉ với ETA/EDA features) | 2 tuần |
| **Phase 2** | Feature engineering (driver behavioral + spatial), LightGBM, offline eval | 2 tuần |
| **Phase 3** | Feature store (Redis), inference service, infrastructure (Terraform + EKS) | 2 tuần |
| **Phase 4** | Shadow deployment (CRP score song song, không ảnh hưởng matching), monitoring setup | 2 tuần |
| **Phase 5** | A/B test (CRP matching vs no-CRP matching), canary rollout | 2 tuần |
| **Phase 6** | Ride-pooling & chaining features, advanced monitoring, feedback loop handling | Ongoing |

---

## Tham khảo kiến trúc folder

Xem `README.md` tại root project cho full folder structure. Các file key:

- `configs/feature_config.yaml` — Định nghĩa feature groups, excluded features
- `configs/model_config.yaml` — Hyperparameters, calibration config
- `configs/monitoring_config.yaml` — Drift thresholds, alerting
- `src/features/transformations.py` — Feature engineering code
- `src/models/train.py` — Training orchestrator
- `src/inference/predictor.py` — Serving endpoint
- `src/monitoring/drift_detection.py` — PSI, KL-divergence
- `infrastructure/terraform/` — AWS infra (SageMaker training + EKS serving)
- `infrastructure/helm/` — Helm charts cho K8s deployment
- `infrastructure/k8s/istio/` — Canary deployment config
