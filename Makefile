.PHONY: setup train test lint deploy generate-data infra-plan infra-apply infra-bootstrap \
        mlflow-experiment mlflow-ui mlflow-report mlflow-upload-s3

ENV ?= dev
PYTHON ?= venv\Scripts\python.exe

setup:
	pip install -e ".[dev]"
	pre-commit install

generate-data:
	python scripts/generate_synthetic_data.py --num-rows 5000

train:
	python -m pipelines.training.pipeline

train-tune:
	python -m src.models.train --config configs/model_config.yaml --tune

evaluate:
	python -m src.evaluation.comparison --config configs/model_config.yaml

test:
	pytest tests/ -v --cov=src

test-data:
	pytest tests/data_validation/ -v

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/

# ── MLflow (offline — không cần Terraform/EKS) ──────────────────────────────
mlflow-experiment:  ## Chạy 4 models, log toàn bộ vào experiment crp-model-comparison
	$(PYTHON) scripts/mlflow_experiment.py

mlflow-experiment-full:  ## Chạy với full 500k rows (chậm hơn)
	$(PYTHON) scripts/mlflow_experiment.py --full-data

mlflow-ui:  ## Mo MLflow dashboard tai http://127.0.0.1:5000
	$(PYTHON) -m mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000

mlflow-report:  ## Mở notebook so sánh metrics
	$(PYTHON) -m jupyter notebook notebooks/mlflow_model_comparison.ipynb

mlflow-upload-s3:  ## (Bonus) Upload mlruns/ artifacts lên S3
	$(PYTHON) scripts/upload_artifacts_s3.py --bucket mlops-lab-wine-quality-bignoht

mlflow-upload-s3-dry:  ## Preview files sẽ upload (không thực sự upload)
	$(PYTHON) scripts/upload_artifacts_s3.py --dry-run

# Docker
docker-train:
	docker build -f infrastructure/docker/Dockerfile.training -t ride-matching-training .

docker-inference:
	docker build -f infrastructure/docker/Dockerfile.inference -t ride-matching-inference .

# Infrastructure
# Secrets được load từ .env (gitignored) — copy từ .env.example và điền giá trị
-include .env
export

infra-init:
	cd infrastructure/terraform/environments/$(ENV) && terraform init

# Lần đầu tiên: tạo EKS cluster trước để kubernetes/helm provider có endpoint
# Sau đó chạy infra-apply để deploy phần còn lại
infra-bootstrap:
	cd infrastructure/terraform/environments/$(ENV) && terraform apply \
		-target=module.networking \
		-target=module.data_lake \
		-target=module.eks \
		-target=module.feature_store

infra-plan:
	cd infrastructure/terraform/environments/$(ENV) && terraform plan

infra-apply:
	cd infrastructure/terraform/environments/$(ENV) && terraform apply

infra-destroy:
	cd infrastructure/terraform/environments/$(ENV) && terraform destroy

# Deployment
deploy:
	python deployment/sagemaker/model_deploy.py --env $(ENV)

rollback:
	bash deployment/scripts/rollback.sh $(ENV)
