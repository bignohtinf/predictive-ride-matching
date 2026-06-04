resource "aws_ecr_repository" "training" {
    name                 = "${var.project}-${var.env}-crp-training"
    image_tag_mutability = "IMMUTABLE"

    image_scanning_configuration {
        scan_on_push = true
    }

    encryption_configuration {
        encryption_type = "AES256"
    }

    tags = {
        Name = "${var.project}-${var.env}-crp-training"
    }
}

resource "aws_ecr_repository" "inference" {
    name                 = "${var.project}-${var.env}-crp-inference"
    image_tag_mutability = "IMMUTABLE"

    image_scanning_configuration {
        scan_on_push = true
    }

    encryption_configuration {
        encryption_type = "AES256"
    }

    tags = {
        Name = "${var.project}-${var.env}-crp-inference"
    }
}

resource "aws_ecr_lifecycle_policy" "training" {
    repository = aws_ecr_repository.training.name

    policy = jsonencode({
        rules = [
            {
                rulePriority = 1
                description  = "Keep only the latest ${var.ecr_image_keep_count} training images"
                selection = {
                    tagStatus   = "any"
                    countType   = "imageCountMoreThan"
                    countNumber = var.ecr_image_keep_count
                }
                action = {
                    type = "expire"
                }
            }
        ]
    })
}

resource "aws_ecr_lifecycle_policy" "inference" {
    repository = aws_ecr_repository.inference.name

    policy = jsonencode({
        rules = [
            {
                rulePriority = 1
                description  = "Keep only the latest ${var.ecr_image_keep_count} inference images"
                selection = {
                    tagStatus   = "any"
                    countType   = "imageCountMoreThan"
                    countNumber = var.ecr_image_keep_count
                }
                action = {
                    type = "expire"
                }
            }
        ]
    })
}

resource "aws_iam_role" "sagemaker_execution" {
    name = "${var.project}-${var.env}-sagemaker-execution-role"

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Principal = {
                    Service = "sagemaker.amazonaws.com"
                }
                Action = "sts:AssumeRole"
            }
        ]
    })

    tags = {
        Name = "${var.project}-${var.env}-sagemaker-execution-role"
  }
}

resource "aws_iam_role_policy" "sagemaker_s3" {
    name = "${var.project}-${var.env}-sagemaker-s3-policy"
    role = aws_iam_role.sagemaker_execution.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Sid    = "ReadWriteProjectBuckets"
                Effect = "Allow"
                Action = [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation"
                ]
                Resource = [
                    "arn:aws:s3:::${var.data_bucket_name}",
                    "arn:aws:s3:::${var.data_bucket_name}/*",
                    "arn:aws:s3:::${var.model_bucket_name}",
                    "arn:aws:s3:::${var.model_bucket_name}/*"
                ]
            }
        ]
    })
}

resource "aws_iam_role_policy" "sagemaker_ecr" {
    name = "${var.project}-${var.env}-sagemaker-ecr-policy"
    role = aws_iam_role.sagemaker_execution.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Sid    = "EcrAuth"
                Effect = "Allow"
                Action = [
                    "ecr:GetAuthorizationToken"
                ]
                Resource = "*"
            },
            {
                Sid    = "PullTrainingAndInferenceImages"
                Effect = "Allow"
                Action = [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:BatchGetImage",
                    "ecr:DescribeImages",
                    "ecr:GetDownloadUrlForLayer"
                ]
                Resource = [
                    aws_ecr_repository.training.arn,
                    aws_ecr_repository.inference.arn
                ]
            }
        ]
    })
}

resource "aws_iam_role_policy" "sagemaker_cloudwatch" {
    name = "${var.project}-${var.env}-sagemaker-cloudwatch-policy"
    role = aws_iam_role.sagemaker_execution.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Action = [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                    "cloudwatch:PutMetricData"
                ]
                Resource = "*"
            }
        ]
    })
}

resource "aws_sagemaker_model_package_group" "crp" {
    model_package_group_name = "${var.project}-${var.env}-crp-models"

    model_package_group_description = "Model registry for Completion Rate Prediction models"

    tags = {
        Name = "${var.project}-${var.env}-crp-models"
    }
}

# ---------------------------------------------------------------------------
# SageMaker Managed MLflow Tracking Server (GA Nov 2024)
# Artifact store: s3://<model_bucket>/mlflow-artifacts/
# ---------------------------------------------------------------------------

resource "aws_sagemaker_mlflow_tracking_server" "this" {
  tracking_server_name = "${var.project}-${var.env}-mlflow"
  artifact_store_uri   = "s3://${var.model_bucket_name}/mlflow-artifacts"
  role_arn             = aws_iam_role.sagemaker_execution.arn
  mlflow_version       = "2.13.2"
  tracking_server_size = "Small"

  tags = {
    Name = "${var.project}-${var.env}-mlflow"
  }
}

resource "aws_iam_role_policy" "sagemaker_mlflow" {
  name = "${var.project}-${var.env}-sagemaker-mlflow-policy"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "MLflowServerAccess"
        Effect = "Allow"
        Action = [
          "sagemaker:GetMlflowTrackingServer",
          "sagemaker:CreatePresignedMlflowTrackingServerUrl"
        ]
        Resource = aws_sagemaker_mlflow_tracking_server.this.arn
      }
    ]
  })
}
