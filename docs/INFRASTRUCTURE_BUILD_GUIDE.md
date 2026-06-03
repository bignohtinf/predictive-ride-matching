# Hướng dẫn tự xây dựng hạ tầng End-to-End

Tài liệu này hướng dẫn bạn **tự tay** xây dựng toàn bộ hạ tầng MLOps cho bài toán Completion Rate Prediction. Không có code mẫu — chỉ có kiến thức nền, lý do thiết kế, thứ tự triển khai, và gợi ý keyword để tự research.

---

## Mục lục

1. [Tổng quan kiến trúc & Thứ tự build](#1-tổng-quan-kiến-trúc--thứ-tự-build)
2. [Phase 1: Networking Foundation](#2-phase-1-networking-foundation)
3. [Phase 2: Data Lake & Storage](#3-phase-2-data-lake--storage)
4. [Phase 3: EKS Cluster](#4-phase-3-eks-cluster)
5. [Phase 4: Feature Store](#5-phase-4-feature-store)
6. [Phase 5: Training Pipeline](#6-phase-5-training-pipeline)
7. [Phase 6: Inference Service trên K8s](#7-phase-6-inference-service-trên-k8s)
8. [Phase 7: CI/CD Pipeline](#8-phase-7-cicd-pipeline)
9. [Phase 8: Monitoring & Observability](#9-phase-8-monitoring--observability)
10. [Phase 9: Canary Deployment với Istio](#10-phase-9-canary-deployment-với-istio)
11. [Terraform — Cách tổ chức module](#11-terraform--cách-tổ-chức-module)
12. [Checklist tự kiểm tra](#12-checklist-tự-kiểm-tra)

---

## 1. Tổng quan kiến trúc & Thứ tự build

### 1.1 Nguyên tắc thiết kế

- **SageMaker cho Training**: Managed, spot instances, tự cleanup — không cần maintain GPU infra
- **EKS cho Serving**: Long-running service, cần auto-scaling, rolling update, canary — đây là nơi học K8s
- **Terraform cho IaC**: Mọi thứ reproducible, version-controlled, multi-environment
- **Redis cho Feature Store online**: Sub-millisecond lookup, phù hợp latency budget

### 1.2 Dependency Graph — Build theo thứ tự này

```
Phase 1: Networking (VPC, Subnets, Security Groups)
    │
    ├── Phase 2: Data Lake (S3, Glue)
    │
    ├── Phase 3: EKS Cluster ──────────────────────┐
    │                                               │
    ├── Phase 4: Feature Store (Redis, SageMaker FS)│
    │                                               │
    └── Phase 5: Training Pipeline (SageMaker, ECR) │
                                                    │
                              Phase 6: Inference Service (Deployment, HPA, Ingress)
                                                    │
                              Phase 7: CI/CD (CodeBuild/GitHub Actions → ECR → EKS)
                                                    │
                              Phase 8: Monitoring (CloudWatch, Prometheus, Grafana)
                                                    │
                              Phase 9: Canary (Istio VirtualService, DestinationRule)
```

Mỗi phase phụ thuộc vào phase trước. Không thể deploy inference service nếu chưa có EKS cluster. Không thể setup canary nếu chưa có inference service chạy ổn.

---

## 2. Phase 1: Networking Foundation

### Tại sao cần?

Mọi service AWS đều sống trong VPC. Không có network foundation = không deploy được gì.

### Bạn cần tạo gì?

| Resource | Mục đích | Lưu ý |
|----------|---------|-------|
| VPC | Isolated network cho toàn project | CIDR đủ rộng (ví dụ /16 = 65K IPs) |
| Private Subnets (≥2 AZs) | EKS nodes, Redis, SageMaker endpoints | Không expose ra internet |
| Public Subnets (≥2 AZs) | NAT Gateway, ALB (load balancer) | Cần cho traffic vào từ ngoài |
| NAT Gateway | Cho private subnets truy cập internet (pull images, call APIs) | Đặt ở public subnet |
| Internet Gateway | Cho public subnets | Attach vào VPC |
| Route Tables | Routing rules: private → NAT, public → IGW | Mỗi loại subnet 1 route table |
| Security Groups | Firewall rules: ai được nói chuyện với ai | Principle of least privilege |

### Bạn cần suy nghĩ gì?

- EKS yêu cầu subnets ở ít nhất 2 Availability Zones. Tại sao? (High availability)
- Tại sao đặt Redis ở private subnet? (Không expose data store ra internet)
- NAT Gateway có chi phí. Dev environment có cần không? (Có — để pull Docker images)
- Security Group cho Redis chỉ cho phép traffic từ EKS nodes và SageMaker. Làm sao enforce?

### Keywords để research

`aws vpc terraform`, `public vs private subnet`, `nat gateway vs vpc endpoint`, `eks networking requirements`, `security group vs nacl`

---

## 3. Phase 2: Data Lake & Storage

### Tại sao cần?

Data pipeline cần nơi lưu trữ: raw data từ source, processed data sau khi clean, feature datasets cho training, model artifacts sau khi train.

### Bạn cần tạo gì?

| Resource | Mục đích | Config quan trọng |
|----------|---------|-------------------|
| S3 Bucket — Data | Lưu raw/processed/features | Versioning ON, encryption KMS, lifecycle rules (raw → Glacier sau 90 ngày) |
| S3 Bucket — Models | Lưu model artifacts (.tar.gz) | Versioning ON (rollback model cũ), restrict access |
| Glue Catalog Database | Metadata catalog cho data | Schema-on-read, dùng với Athena để query |
| Glue Crawler | Auto-discover schema từ S3 | Schedule mỗi 6h, crawl raw/ prefix |

### Bạn cần suy nghĩ gì?

- Bucket naming convention: phải globally unique. Pattern: `{project}-{purpose}-{env}` (ví dụ: `ride-matching-data-dev`)
- Tại sao cần 2 buckets riêng (data vs models)? (Separation of concerns, access control khác nhau)
- Lifecycle rule: raw data truy cập ít sau 90 ngày → chuyển Glacier tiết kiệm cost
- Cross-account access: staging/prod có thể cần đọc model từ bucket khác
- S3 bucket policy vs IAM policy: khi nào dùng cái nào?

### Keywords để research

`s3 bucket terraform`, `s3 versioning`, `s3 lifecycle glacier`, `aws glue catalog terraform`, `s3 kms encryption`

---

## 4. Phase 3: EKS Cluster

### Tại sao EKS thay vì tự dựng K8s?

EKS quản lý control plane (API server, etcd, scheduler) cho bạn. Bạn chỉ cần quản lý worker nodes. Self-managed K8s là nightmare trong production — upgrade, patching, HA cho etcd đều phức tạp.

### Bạn cần tạo gì?

| Resource | Mục đích | Config quan trọng |
|----------|---------|-------------------|
| EKS Cluster | K8s control plane | Version (dùng latest stable), endpoint access (private + public) |
| Managed Node Group | Worker nodes chạy pods | Instance type, scaling config (min/max/desired) |
| IRSA (IAM Roles for Service Accounts) | Pods access AWS services | Thay vì gắn IAM role vào node (quá rộng) |
| EKS Add-ons | Core components | CoreDNS, kube-proxy, VPC CNI, EBS CSI driver |
| aws-load-balancer-controller | Tạo ALB từ Ingress resource | Quan trọng nhất cho traffic vào |
| cluster-autoscaler (hoặc Karpenter) | Auto-scale nodes | Khi pods pending do thiếu resource |

### Bạn cần suy nghĩ gì?

- **Node sizing**: Inference service cần bao nhiêu CPU/memory? 7.6M records train → model size? Mỗi pod serve bao nhiêu concurrent requests?
- **Spot vs On-demand nodes**: Spot rẻ 60-70% nhưng có thể bị reclaim. Inference service cần reliability → On-demand. Batch jobs (feature compute) → Spot OK.
- **IRSA vs Node IAM role**: IRSA cho phép mỗi pod có IAM role riêng (pod A đọc S3, pod B đọc Redis, không phải cả 2 đều được làm cả 2). Đây là security best practice.
- **Private endpoint**: EKS API server nên private (chỉ access từ trong VPC hoặc qua VPN). Public endpoint = attack surface.
- **Node Group vs Fargate**: Fargate = serverless (không quản lý nodes). Đơn giản hơn nhưng ít control, cold start cao hơn. Cho inference service, node group tốt hơn.

### Kubernetes concepts bạn sẽ đụng

Khi dựng EKS xong, bạn sẽ bắt đầu tạo K8s resources. Hiểu flow:

```
User request → ALB (Ingress) → Service → Pod(s) → Container (inference code)
```

| K8s Resource | Vai trò | Tương đương trong EC2 world |
|---|---|---|
| Namespace | Isolation logic (dev/staging/prod trong cùng cluster) | Separate VPC |
| Deployment | Quản lý replicas, rolling update | Auto Scaling Group |
| Pod | Đơn vị nhỏ nhất chạy container | EC2 instance |
| Service (ClusterIP) | Internal load balancing giữa pods | Internal ELB |
| Ingress | External load balancing, routing rules | Application Load Balancer |
| HPA | Auto-scale pods theo CPU/memory/custom metrics | ASG scaling policy |
| PDB (PodDisruptionBudget) | Đảm bảo min pods available khi rolling update | — |
| ConfigMap | Config không nhạy cảm (model path, feature list) | Parameter Store |
| Secret | Config nhạy cảm (Redis password, API keys) | Secrets Manager |
| ServiceAccount + IRSA | Pod-level AWS permissions | IAM role |

### Keywords để research

`eks terraform module`, `eks managed node group`, `irsa terraform`, `aws-load-balancer-controller eks`, `eks cluster autoscaler vs karpenter`, `eks private endpoint`, `eks add-ons`

---

## 5. Phase 4: Feature Store

### Tại sao cần Feature Store?

CRP model cần 2 loại features:
- **Batch features** (driver_completion_rate_7d, area_stats): Precomputed, thay đổi mỗi vài giờ
- **Real-time features** (ETA, num_drivers): Có sẵn trong matching context

Batch features phải được serve với latency < 1ms vì nằm trong critical path của matching pipeline.

### Bạn cần tạo gì?

| Resource | Mục đích | Config quan trọng |
|----------|---------|-------------------|
| ElastiCache Redis (Replication Group) | Online feature serving | Node type, num nodes, encryption, subnet group |
| SageMaker Feature Group | Offline feature store (training data) | Record identifier, event time, feature definitions |
| Lambda hoặc Glue Job | Compute batch features → push vào Redis | Schedule mỗi 6h, chạy trên data mới nhất |

### Bạn cần suy nghĩ gì?

- **Redis data model**: Key = `driver:{driver_id}`, Value = hash chứa features. Hay dùng sorted set? Trade-off giữa memory và access pattern.
- **TTL**: Features nên expire sau bao lâu? `driver_completion_rate_7d` nên TTL = 24h (refresh daily). Nếu miss cache → dùng default value.
- **Redis cluster mode vs replication mode**: Cluster mode shards data → scale horizontally. Replication mode = read replicas → scale reads. Với 7.6M records, dataset features fit in memory (ước tính: 500K unique drivers × 10 features × 8 bytes ≈ 40MB). Replication mode đủ.
- **Failover**: Nếu Redis down, inference service làm gì? (Dùng default values, degrade gracefully, KHÔNG crash)
- **Consistency**: Feature computed lúc 2AM, nhưng model predict lúc 3PM. Data stale 13h có acceptable không? (Thường OK cho daily features, NOT OK cho hourly features)

### Keywords để research

`elasticache redis terraform`, `elasticache replication group`, `redis data modeling features`, `sagemaker feature group terraform`, `feature store architecture patterns`

---

## 6. Phase 5: Training Pipeline

### Tại sao SageMaker Training (không phải train trên EKS)?

- Training là **batch job** — chạy xong tắt. Không cần long-running infrastructure.
- SageMaker spot instances tiết kiệm 60-70% cost.
- Automatic cleanup: instance tự terminate sau khi train xong.
- Built-in experiment tracking, hyperparameter tuning.
- Nếu train trên EKS: phải maintain GPU nodes (đắt khi idle), handle spot interruption manually, phức tạp hơn mà không thêm giá trị.

### Bạn cần tạo gì?

| Resource | Mục đích | Config quan trọng |
|----------|---------|-------------------|
| ECR Repository (training) | Lưu Docker image cho training | Lifecycle policy (giữ 10 images gần nhất) |
| ECR Repository (inference) | Lưu Docker image cho serving | Image scanning ON |
| SageMaker Model Package Group | Model Registry — versioning & approval | Tên group theo project-env |
| IAM Role cho SageMaker | Permissions: S3 read/write, ECR pull, CloudWatch logs | Least privilege |
| Step Functions (optional) | Orchestrate training pipeline end-to-end | Nếu muốn fully automated |

### Training Flow bạn sẽ build

```
1. Data Extract (Glue/Athena query → S3 raw)
       ↓
2. Data Validation (Great Expectations check schema/distribution)
       ↓
3. Feature Engineering (Python job → S3 features)
       ↓
4. Train (SageMaker Training Job: pull image từ ECR, đọc data từ S3, output model → S3)
       ↓
5. Evaluate (So sánh với champion model trên holdout set)
       ↓
6. Register (Nếu pass threshold → đăng ký vào Model Registry, status = PendingApproval)
       ↓
7. Approve (Manual hoặc auto → trigger deployment)
```

### Bạn cần suy nghĩ gì?

- **Spot interruption handling**: SageMaker spot training tự retry nếu bị interrupt. Cần set `max_wait_time` (tổng thời gian chờ). Nếu job mất 1h train → set max_wait = 2h.
- **Model artifact format**: LightGBM model + calibrator + feature list + metrics, đóng gói thành `model.tar.gz` push lên S3. Inference service sẽ pull artifact này.
- **Champion-Challenger**: Luôn giữ model đang chạy production (champion). Model mới (challenger) phải beat champion trên test set trước khi promote.
- **Reproducibility**: Ghi lại: data version (S3 path + timestamp), code version (git commit), hyperparameters, random seed. Phải reproduce được kết quả.

### Keywords để research

`sagemaker training job terraform`, `ecr repository terraform`, `sagemaker model registry`, `sagemaker spot training`, `step functions ml pipeline`, `sagemaker pipeline`

---

## 7. Phase 6: Inference Service trên K8s

### Đây là nơi bạn học K8s nhiều nhất

Inference service là long-running HTTP server nhận requests từ matching engine, return CRP scores. Đây là core K8s workload.

### Bạn cần tạo gì? (K8s Resources)

| Resource | File | Mục đích |
|----------|------|---------|
| Namespace | `namespace.yaml` | Isolate inference workload |
| Deployment | `deployment.yaml` | Định nghĩa pods: image, replicas, resources, probes |
| Service | `service.yaml` | ClusterIP — internal load balancing |
| Ingress | `ingress.yaml` | ALB — external traffic routing |
| HPA | `hpa.yaml` | Auto-scale pods theo metrics |
| ConfigMap | `configmap.yaml` | Model path, feature config, Redis endpoint |
| Secret | `secret.yaml` | Redis password, AWS credentials |
| ServiceAccount | `serviceaccount.yaml` | IRSA — pod-level AWS permissions |
| PDB | `pdb.yaml` | Min available pods khi disruption |

### Chi tiết từng resource — Bạn cần suy nghĩ gì

**Deployment:**
- `replicas`: Bao nhiêu pods ban đầu? (Hint: tính từ throughput requirement)
- `resources.requests` vs `resources.limits`: Request = guaranteed, limit = max allowed. Set sai → pod bị OOM kill hoặc lãng phí.
- `readinessProbe`: Khi nào pod sẵn sàng nhận traffic? (Model loaded xong, warm-up xong)
- `livenessProbe`: Khi nào pod chết và cần restart? (Health check fail)
- `strategy.rollingUpdate`: `maxSurge` (thêm bao nhiêu pod mới), `maxUnavailable` (cho phép mất bao nhiêu pod cùng lúc)
- **Init container**: Pull model artifact từ S3 vào shared volume trước khi main container start

**HPA (Horizontal Pod Autoscaler):**
- Scale theo metric nào? CPU? Memory? Custom metric (request latency p99)?
- `minReplicas` / `maxReplicas`: Min = đảm bảo availability, Max = budget cap
- `targetCPUUtilizationPercentage`: 70% là common target. Quá cao → latency spike khi burst. Quá thấp → lãng phí.
- `behavior.scaleDown.stabilizationWindowSeconds`: Tránh flapping (scale up rồi scale down liên tục)

**Ingress:**
- Annotations cho AWS ALB: scheme (internal vs internet-facing), target-type (ip vs instance)
- Health check path: `/ping` hoặc `/health`
- Matching engine gọi inference service qua internal ALB (không cần internet-facing)

**PDB (PodDisruptionBudget):**
- `minAvailable: 2` → luôn có ít nhất 2 pods serving khi K8s cần drain node (maintenance, upgrade)
- Nếu không có PDB: rolling update có thể terminate tất cả pods cùng lúc → downtime

### Resource Sizing — Cách tính

```
Yêu cầu: 5000 pairs / 500ms = 10,000 predictions/second

Benchmark (cần tự đo):
- 1 pod (4 CPU, 8GB RAM) serve được ~2000 req/s (LightGBM batch predict)

→ Min pods = 10,000 / 2,000 = 5 pods
→ HPA max = 5 × 3 = 15 pods (cho peak 3x traffic)
→ Node group min = ceil(5 pods / pods_per_node)
```

Bạn cần benchmark thực tế vì phụ thuộc vào: model size, feature count, batch size.

### Keywords để research

`kubernetes deployment yaml`, `kubernetes hpa custom metrics`, `kubernetes ingress aws alb`, `kubernetes readiness vs liveness probe`, `kubernetes resource requests limits`, `kubernetes pdb`, `kubernetes init container s3`

---

## 8. Phase 7: CI/CD Pipeline

### Tại sao cần CI/CD cho ML?

ML system có 2 loại thay đổi:
- **Code change**: Sửa feature engineering, model architecture, preprocessing → trigger CI/CD giống software thông thường
- **Model change**: Retrain với data mới → model artifact mới → cần deploy lên K8s

CI/CD phải handle cả 2.

### Pipeline Flow

```
Code Push → CI (lint, test, build image) → Push to ECR
                                                ↓
Model Retrain → New artifact in S3 → Trigger CD
                                                ↓
                              CD: Update K8s Deployment (new image tag / new model path)
                                                ↓
                              Rolling Update (hoặc Canary via Istio)
```

### Bạn cần tạo gì?

| Component | Mục đích | Tool options |
|-----------|---------|--------------|
| CI Pipeline | Lint, unit test, build Docker image, push ECR | GitHub Actions / CodeBuild |
| CD Pipeline | Deploy new image/model lên EKS | ArgoCD / Flux / GitHub Actions + kubectl |
| Image Tag Strategy | Xác định version nào đang chạy | Git commit SHA (không dùng `latest` tag!) |
| Model Deployment Trigger | Khi model mới approved → auto deploy | EventBridge → Lambda → update K8s |

### Bạn cần suy nghĩ gì?

- **GitOps (ArgoCD/Flux) vs Push-based (kubectl apply)**: GitOps = K8s state luôn sync với git repo. Push-based = CI pipeline chủ động apply changes. GitOps an toàn hơn, có audit trail, dễ rollback.
- **Image tag `latest` là anti-pattern**: Tại sao? (K8s cache image, không biết version nào đang chạy, không rollback được)
- **Khi nào trigger model deployment?**
  - Option A: Tự động khi model registry có new version approved
  - Option B: Manual approval (production)
  - Recommend: Auto cho dev/staging, manual cho prod
- **Rollback strategy**: Nếu model mới degrade metrics → rollback K8s deployment về revision trước (model cũ vẫn còn trong S3)

### Keywords để research

`github actions eks deploy`, `argocd eks`, `ecr image scanning`, `kubernetes rolling update strategy`, `gitops vs push deployment`, `sagemaker model registry eventbridge`

---

## 9. Phase 8: Monitoring & Observability

### 3 pillars: Metrics, Logs, Traces

Inference service chạy trên K8s cần monitor ở 3 tầng:

**Tầng 1 — Infrastructure:**
- Node CPU/memory utilization
- Pod restarts, OOM kills
- Cluster health

**Tầng 2 — Application:**
- Request latency (p50, p95, p99)
- Throughput (req/s)
- Error rate (4xx, 5xx)
- Model inference time

**Tầng 3 — ML-specific:**
- Prediction distribution drift
- Feature drift (PSI)
- Actual vs predicted completion rate
- Calibration drift (ECE over time)

### Bạn cần tạo gì?

| Component | Mục đích | Tool |
|-----------|---------|------|
| Prometheus | Collect metrics từ pods (application + infra) | Helm chart: kube-prometheus-stack |
| Grafana | Dashboard visualization | Bundled với kube-prometheus-stack |
| CloudWatch | AWS service metrics (SageMaker, Redis, S3) | Native integration |
| CloudWatch Alarms | Alert khi threshold breached | SNS → Email/Slack |
| Lambda (drift detector) | Chạy scheduled drift check | EventBridge trigger mỗi 6h |
| Custom metrics exporter | Expose ML metrics (PSI, ECE) cho Prometheus | Python sidecar hoặc pushgateway |

### Bạn cần suy nghĩ gì?

- **Prometheus trong K8s**: Deploy bằng Helm (`kube-prometheus-stack`). Nó auto-discover pods có annotation `prometheus.io/scrape: "true"` và scrape metrics.
- **Application metrics**: Inference service cần expose `/metrics` endpoint (format Prometheus). Dùng library (Python: `prometheus_client`) để track: prediction latency histogram, prediction value histogram, request count.
- **Alert fatigue**: Quá nhiều alerts = ignore tất cả. Chỉ alert actionable things. Chia thành: WARNING (investigate khi rảnh) vs CRITICAL (cần action ngay).
- **Label delay cho ML monitoring**: Completion status chỉ biết sau 30 phút - 2 giờ. Concept drift monitoring luôn bị delay → cần prediction drift (real-time proxy) để detect sớm.
- **Grafana dashboard nên có**: Inference latency, throughput, error rate, pod count, prediction distribution (histogram), feature distribution top-5, actual vs predicted completion rate (rolling 24h).

### Keywords để research

`kube-prometheus-stack helm`, `prometheus python client`, `grafana kubernetes dashboard`, `cloudwatch container insights eks`, `ml monitoring evidently`, `prometheus custom metrics kubernetes`

---

## 10. Phase 9: Canary Deployment với Istio

### Tại sao cần Canary?

Model mới có thể perform tốt offline nhưng fail production (distribution shift, latency regression, unexpected edge cases). Canary deployment = roll out model mới cho 5% traffic trước, monitor, rồi tăng dần.

### Istio là gì?

Service mesh — một layer chạy cạnh (sidecar) mỗi pod, intercept mọi network traffic. Cho phép:
- **Traffic splitting**: 95% → model cũ, 5% → model mới
- **Observability**: Latency, error rate per version tự động
- **Circuit breaking**: Nếu model mới error rate > threshold → tự redirect 100% về model cũ

### Bạn cần tạo gì?

| Resource | Mục đích | Lưu ý |
|----------|---------|-------|
| Istio installation | Service mesh trên EKS | Helm hoặc istioctl |
| Gateway | Entry point cho traffic vào mesh | Thay thế hoặc bổ sung Ingress |
| VirtualService | Traffic routing rules (weight-based split) | Route theo header hoặc percentage |
| DestinationRule | Định nghĩa subsets (v1, v2) | Map với Deployment labels |

### Canary Flow

```
1. Deploy model mới (Deployment v2) với label version=v2, replicas=1
2. Update VirtualService: 95% → v1, 5% → v2
3. Monitor 1-2h: latency, error rate, prediction distribution, completion rate
4. Nếu OK: tăng 25% → 50% → 100%
5. Nếu fail: rollback VirtualService về 100% → v1, delete Deployment v2
```

### Bạn cần suy nghĩ gì?

- **Istio sidecar injection**: Enable per namespace (`istio-injection=enabled` label). Mỗi pod sẽ tự động có Envoy proxy sidecar.
- **Resource overhead**: Mỗi sidecar thêm ~50MB memory, ~10ms latency. Có acceptable cho latency budget không? (Thường OK vì 10ms << 500ms budget)
- **Automated canary**: Tools như Flagger tự động tăng traffic nếu metrics OK, rollback nếu không. Không cần manual.
- **Header-based routing**: Ngoài percentage-based, có thể route traffic có header `x-model-version: v2` sang model mới → testing riêng trước khi public canary.
- **A/B test vs Canary**: Canary = giảm risk khi deploy. A/B test = so sánh 2 versions với statistical significance. Canary ngắn (hours), A/B test dài (days/weeks).

### Keywords để research

`istio eks terraform`, `istio virtualservice traffic splitting`, `istio canary deployment`, `flagger automated canary`, `istio destination rule subsets`, `istio gateway vs kubernetes ingress`

---

## 11. Terraform — Cách tổ chức module

### Module Structure

```
infrastructure/terraform/
├── main.tf              ← Gọi tất cả modules, wiring outputs/inputs
├── variables.tf         ← Input variables (region, env, instance types)
├── outputs.tf           ← Export values (endpoint URLs, ARNs)
├── providers.tf         ← AWS provider config, required versions
├── backend.tf           ← Remote state (S3 + DynamoDB lock)
├── modules/
│   ├── networking/      ← VPC, subnets, SGs
│   ├── data-lake/       ← S3, Glue
│   ├── eks/             ← EKS cluster, node groups, add-ons
│   ├── eks-serving/     ← ALB controller, namespace setup
│   ├── feature-store/   ← Redis, SageMaker Feature Group
│   ├── training/        ← ECR, Model Registry
│   ├── monitoring/      ← CloudWatch, SNS, Lambda
│   ├── cicd/            ← CodeBuild/CodePipeline
│   └── iam/             ← All IAM roles & policies
└── environments/
    ├── dev/main.tf      ← Gọi root module với dev params
    ├── staging/main.tf
    └── prod/main.tf
```

### Nguyên tắc module

1. **Mỗi module = 1 concern**: Networking biết về VPC, không biết về EKS. EKS nhận subnet_ids làm input.
2. **Module communication qua outputs/variables**: Module A export `vpc_id` → Root module truyền vào Module B.
3. **DRY via environments**: Root module chứa logic, environments chỉ truyền parameters khác nhau (instance size, replica count).
4. **Remote state**: Terraform state file phải lưu S3 (không local). DynamoDB table cho state locking (tránh 2 người apply cùng lúc).

### Thứ tự apply

```bash
# Lần đầu: tạo S3 bucket + DynamoDB table cho remote state (chicken-egg problem)
# → Tạo manual hoặc dùng separate terraform config

# Sau đó:
terraform init          # Download providers, configure backend
terraform plan          # Preview changes
terraform apply         # Apply changes

# Module dependencies tự resolve qua depends_on và output references
```

### Bạn cần suy nghĩ gì?

- **State locking**: 2 người chạy `terraform apply` cùng lúc = corrupt state. DynamoDB table lock giải quyết.
- **Environment isolation**: Dev/staging/prod dùng CÙNG modules nhưng KHÁC parameters và KHÁC state files. Không bao giờ share state giữa environments.
- **Secrets trong Terraform**: KHÔNG hardcode passwords/keys trong .tf files. Dùng `terraform.tfvars` (gitignored) hoặc environment variables hoặc AWS Secrets Manager data source.
- **Module versioning**: Khi module thay đổi, tất cả environments apply. Nếu muốn pin version → dùng git tags hoặc Terraform Registry.

### Keywords để research

`terraform module structure best practices`, `terraform remote state s3 dynamodb`, `terraform workspace vs directory environments`, `terraform sensitive variables`, `terraform depends_on`

---

## 12. Checklist tự kiểm tra

Sau mỗi phase, tự verify trước khi sang phase tiếp:

### Phase 1: Networking
- [ ] VPC tạo thành công, có DNS support
- [ ] Private subnets ở ≥ 2 AZs
- [ ] Instance trong private subnet ping được internet (qua NAT)
- [ ] Security groups: Redis SG chỉ cho phép traffic từ EKS SG

### Phase 2: Data Lake
- [ ] Upload file test lên S3 → đọc được từ SageMaker role
- [ ] Glue Crawler chạy thành công, table xuất hiện trong Catalog
- [ ] Versioning hoạt động (upload 2 lần cùng key → 2 versions)

### Phase 3: EKS
- [ ] `kubectl get nodes` thấy nodes Ready
- [ ] Deploy nginx test pod → curl được từ trong cluster
- [ ] ALB Ingress controller hoạt động (tạo Ingress → ALB xuất hiện)
- [ ] IRSA hoạt động: pod với ServiceAccount đọc được S3

### Phase 4: Feature Store
- [ ] Redis connect được từ pod trong EKS
- [ ] Write/read feature → latency < 1ms
- [ ] SageMaker Feature Group ingest thành công

### Phase 5: Training
- [ ] Push Docker image lên ECR thành công
- [ ] SageMaker Training Job chạy, output model.tar.gz lên S3
- [ ] Model registered trong Model Package Group

### Phase 6: Inference
- [ ] Deployment running, pods healthy
- [ ] HPA scale up khi load test
- [ ] `/ping` qua Ingress trả 200
- [ ] `/invocations` trả predictions đúng format
- [ ] Pod restart sau OOM → liveness probe catch

### Phase 7: CI/CD
- [ ] Code push → image build + push ECR tự động
- [ ] New image → K8s Deployment update tự động
- [ ] Rollback hoạt động (revert về revision cũ)

### Phase 8: Monitoring
- [ ] Prometheus scrape được metrics từ inference pods
- [ ] Grafana dashboard hiển thị latency, throughput
- [ ] CloudWatch alarm fire khi simulate high latency
- [ ] Drift detection Lambda chạy scheduled

### Phase 9: Canary
- [ ] Istio sidecar injected vào pods
- [ ] VirtualService split traffic 90/10 → verify bằng request count
- [ ] Rollback VirtualService → 100% v1 hoạt động

---

## Tài liệu tham khảo theo chủ đề

| Chủ đề | Resource |
|--------|----------|
| EKS + Terraform | `github.com/terraform-aws-modules/terraform-aws-eks` |
| K8s concepts | `kubernetes.io/docs/concepts/` |
| Helm | `helm.sh/docs/` |
| Istio | `istio.io/latest/docs/` |
| SageMaker | `docs.aws.amazon.com/sagemaker/` |
| Prometheus trên K8s | `github.com/prometheus-community/helm-charts` |
| MLOps patterns | `ml-ops.org`, `papers.nips.cc (ML Systems)` |
| Feature Store design | `feast.dev/docs/` (open-source feature store) |
