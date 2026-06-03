# Predictive Ride Matching - Completion Rate Prediction

End-to-end MLOps system for predicting ride completion probability in ride-hailing matching.

## Project Structure

```
predictive-ride-matching/
├── configs/                          # Configuration files
│   ├── model_config.yaml             # Model hyperparameters
│   ├── feature_config.yaml           # Feature definitions & transformations
│   ├── pipeline_config.yaml          # Pipeline orchestration config
│   └── monitoring_config.yaml        # Drift thresholds & alerting
│
├── data/                             # Data directory (gitignored)
│   ├── raw/                          # Raw data from source
│   ├── processed/                    # Cleaned & transformed
│   └── features/                     # Feature-engineered datasets
│
├── notebooks/                        # Jupyter notebooks
│   ├── 01_eda.ipynb                  # Exploratory Data Analysis
│   ├── 02_feature_engineering.ipynb  # Feature experiments
│   ├── 03_modeling.ipynb             # Model experiments
│   └── 04_evaluation.ipynb           # Model evaluation & comparison
│
├── src/                              # Source code
│   ├── data/                         # Data ingestion & processing
│   │   ├── __init__.py
│   │   ├── ingestion.py              # Data extraction from warehouse
│   │   ├── validation.py             # Great Expectations data validation
│   │   ├── preprocessing.py          # Cleaning, imputation, outlier handling
│   │   └── synthetic.py              # Synthetic data generation
│   │
│   ├── features/                     # Feature engineering
│   │   ├── __init__.py
│   │   ├── feature_store.py          # Feature store read/write
│   │   ├── batch_features.py         # Precomputed features (driver history, area stats)
│   │   ├── realtime_features.py      # Real-time computed features
│   │   └── transformations.py        # Feature transformations (cyclical, inverse, etc.)
│   │
│   ├── models/                       # Model training
│   │   ├── __init__.py
│   │   ├── train.py                  # Training orchestrator
│   │   ├── lightgbm_model.py         # LightGBM implementation
│   │   ├── xgboost_model.py          # XGBoost implementation
│   │   ├── baseline.py               # Logistic Regression baseline
│   │   ├── calibration.py            # Probability calibration (Platt/Isotonic)
│   │   └── hyperparameter_tuning.py  # Optuna-based tuning
│   │
│   ├── inference/                    # Inference pipeline
│   │   ├── __init__.py
│   │   ├── predictor.py              # SageMaker inference handler
│   │   ├── feature_serving.py        # Real-time feature retrieval
│   │   └── postprocessing.py         # Score calibration & business rules
│   │
│   ├── evaluation/                   # Model evaluation
│   │   ├── __init__.py
│   │   ├── metrics.py                # AUC-ROC, AUC-PR, LogLoss, ECE
│   │   ├── comparison.py             # Champion vs challenger comparison
│   │   └── reports.py                # Evaluation report generation
│   │
│   ├── monitoring/                   # Production monitoring
│   │   ├── __init__.py
│   │   ├── drift_detection.py        # PSI, KL-divergence for data/concept drift
│   │   ├── performance_monitor.py    # Online metric tracking
│   │   └── alerting.py               # Alert trigger logic
│   │
│   └── utils/                        # Shared utilities
│       ├── __init__.py
│       ├── logger.py
│       ├── config.py                 # Config loader
│       └── aws_helpers.py            # S3, SageMaker helper functions
│
├── tests/                            # Tests
│   ├── unit/                         # Unit tests for src modules
│   ├── integration/                  # Integration tests (pipeline, endpoint)
│   └── data_validation/              # Data quality test suites
│
├── pipelines/                        # ML pipeline definitions
│   ├── training/
│   │   ├── step_functions.json       # AWS Step Functions definition
│   │   └── training_pipeline.py      # SageMaker Pipeline definition
│   ├── inference/
│   │   └── inference_pipeline.py
│   └── feature_engineering/
│       └── feature_pipeline.py
│
├── infrastructure/                   # Infrastructure as Code
│   ├── terraform/
│   │   ├── main.tf                   # Root module
│   │   ├── variables.tf              # Input variables
│   │   ├── outputs.tf                # Output values
│   │   ├── providers.tf              # AWS provider config
│   │   ├── backend.tf                # S3 remote state
│   │   ├── modules/
│   │   │   ├── data-lake/            # S3 buckets, Glue catalog
│   │   │   ├── feature-store/        # SageMaker FS + ElastiCache
│   │   │   ├── training/             # SageMaker training + ECR
│   │   │   ├── eks/                  # EKS cluster, node groups, IRSA
│   │   │   ├── eks-serving/          # ALB Ingress, service mesh config
│   │   │   ├── monitoring/           # CloudWatch, SNS, Lambda
│   │   │   ├── cicd/                 # CodePipeline + CodeBuild
│   │   │   ├── networking/           # VPC, subnets, security groups
│   │   │   └── iam/                  # IAM roles & policies
│   │   └── environments/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── prod/
│   ├── helm/                         # Helm charts
│   │   └── completion-rate-predictor/
│   │       ├── templates/            # K8s resource templates
│   │       └── values/               # Per-environment values
│   ├── k8s/                          # Kustomize manifests
│   │   ├── base/                     # Base resources
│   │   ├── overlays/{dev,staging,prod}/
│   │   └── istio/                    # Canary deployment config
│   └── docker/
│       ├── Dockerfile.training       # Training container
│       └── Dockerfile.inference      # Inference container
│
├── deployment/                       # Deployment configs
│   └── scripts/
│       ├── deploy.sh                 # Helm deploy automation
│       └── rollback.sh               # Rollback script
│
├── monitoring/                       # Monitoring configs
│   ├── dashboards/
│   │   └── cloudwatch_dashboard.json
│   └── alerts/
│       └── alert_rules.yaml
│
├── scripts/                          # Utility scripts
│   ├── setup_env.sh                  # Environment setup
│   └── generate_synthetic_data.py    # Data generation script
│
├── .github/
│   └── workflows/
│       ├── ci.yaml                   # Lint, test on PR
│       └── cd.yaml                   # Deploy on merge to main
│
├── .gitignore
├── pyproject.toml                    # Python project config
├── Makefile                          # Common commands
└── README.md
```

## Quick Start

```bash
# Setup
make setup

# Generate synthetic data
make generate-data

# Train model
make train

# Run tests
make test

# Deploy infrastructure
make infra-plan ENV=dev
make infra-apply ENV=dev

# Deploy model
make deploy ENV=dev
```

## Architecture

CRP model predicts `P(is_completed=1)` for each (order, driver) pair at matching time, serving as the **scoring layer** in the Batch Matching pipeline: Candidate Generation → CRP Scoring → Global Optimization (ILP).

**Dataset:** ~7.6M records. **Training:** SageMaker (managed, spot instances). **Serving:** EKS (K8s) via Helm/Kustomize + Istio canary.

**Key constraints:** <10ms p99 per pair (batch inference 1000-5000 pairs trong 500ms budget).

Xem `docs/COMPLETION_RATE_PREDICTION_GUIDE.md` cho full design document.
