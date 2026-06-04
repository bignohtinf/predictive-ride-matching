#!/usr/bin/env python3
"""
Submit a SageMaker Training Job for CRP LightGBM training.

Required env vars:
  TRAINING_IMAGE_URI
  SAGEMAKER_ROLE_ARN
  DATA_BUCKET
  MODEL_BUCKET

Optional env vars:
  AWS_REGION=ap-southeast-1
  PROJECT=crp
  ENV=dev
  TRAINING_INSTANCE_TYPE=ml.m5.xlarge
  TRAINING_INSTANCE_COUNT=1
  MAX_RUNTIME_SECONDS=3600
  USE_SPOT=true
  MAX_WAIT_SECONDS=7200
"""

import os
import time
import boto3


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    region = get_env("AWS_REGION", "ap-southeast-1")
    project = get_env("PROJECT", "crp")
    stage = get_env("ENV", "dev")

    training_image_uri = get_env("TRAINING_IMAGE_URI")
    role_arn = get_env("SAGEMAKER_ROLE_ARN")
    data_bucket = get_env("DATA_BUCKET")
    model_bucket = get_env("MODEL_BUCKET")

    instance_type = get_env("TRAINING_INSTANCE_TYPE", "ml.m5.xlarge")
    instance_count = int(get_env("TRAINING_INSTANCE_COUNT", "1"))
    max_runtime_seconds = int(get_env("MAX_RUNTIME_SECONDS", "3600"))
    use_spot = get_env("USE_SPOT", "true").lower() == "true"
    max_wait_seconds = int(get_env("MAX_WAIT_SECONDS", "7200"))

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    job_name = f"{project}-{stage}-crp-train-{timestamp}"

    sagemaker = boto3.client("sagemaker", region_name=region)

    request = {
        "TrainingJobName": job_name,
        "RoleArn": role_arn,
        "AlgorithmSpecification": {
            "TrainingImage": training_image_uri,
            "TrainingInputMode": "File",
        },
        "InputDataConfig": [
            {
                "ChannelName": "train",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{data_bucket}/features/train/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "text/csv",
            },
            {
                "ChannelName": "validation",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{data_bucket}/features/validation/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "text/csv",
            },
        ],
        "OutputDataConfig": {
            "S3OutputPath": f"s3://{model_bucket}/training-output/"
        },
        "ResourceConfig": {
            "InstanceType": instance_type,
            "InstanceCount": instance_count,
            "VolumeSizeInGB": 30,
        },
        "StoppingCondition": {
            "MaxRuntimeInSeconds": max_runtime_seconds,
        },
        "HyperParameters": {
            "objective": "binary",
            "metric": "binary_logloss,auc",
            "num_leaves": "63",
            "learning_rate": "0.05",
            "max_depth": "10",
            "min_child_samples": "50",
            "subsample": "0.8",
            "colsample_bytree": "0.8",
            "scale_pos_weight": "9.0",
            "early_stopping_rounds": "50",
        },
        "Tags": [
            {"Key": "Project", "Value": project},
            {"Key": "Env", "Value": stage},
            {"Key": "Component", "Value": "training"},
        ],
    }

    if use_spot:
        request["EnableManagedSpotTraining"] = True
        request["StoppingCondition"]["MaxWaitTimeInSeconds"] = max_wait_seconds

    sagemaker.create_training_job(**request)

    print(f"Submitted SageMaker training job: {job_name}")
    print(f"Training data: s3://{data_bucket}/features/train/")
    print(f"Validation data: s3://{data_bucket}/features/validation/")
    print(f"Model output: s3://{model_bucket}/training-output/")


if __name__ == "__main__":
    main()
