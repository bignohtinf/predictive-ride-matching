.PHONY: setup train test lint deploy generate-data infra-plan infra-apply

ENV ?= dev

setup:
	pip install -e ".[dev]"
	pre-commit install

generate-data:
	python scripts/generate_synthetic_data.py --num-rows 5000

train:
	python -m src.models.train --config configs/model_config.yaml

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

# Docker
docker-train:
	docker build -f infrastructure/docker/Dockerfile.training -t ride-matching-training .

docker-inference:
	docker build -f infrastructure/docker/Dockerfile.inference -t ride-matching-inference .

# Infrastructure
infra-init:
	cd infrastructure/terraform/environments/$(ENV) && terraform init

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
