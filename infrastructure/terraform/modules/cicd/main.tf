locals {
  github_oidc_url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url = local.github_oidc_url

  client_id_list = [
    "sts.amazonaws.com"
  ]

  # GitHub Actions OIDC thumbprint. Re-check before production hardening.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]

  tags = {
    Project = var.project
    Env     = var.env
  }
}

data "aws_iam_policy_document" "github_assume_role" {
  statement {
    effect = "Allow"

    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/${var.github_branch}",
        "repo:${var.github_repository}:pull_request"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.project}-${var.env}-github-actions-role"
  assume_role_policy = data.aws_iam_policy_document.github_assume_role.json

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_iam_role_policy" "github_actions" {
  name = "${var.project}-${var.env}-github-actions-policy"
  role = aws_iam_role.github_actions.id

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
        Sid    = "EcrPushPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeImages",
          "ecr:DescribeRepositories",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:ListImages",
          "ecr:PutImage",
          "ecr:UploadLayerPart"
        ]
        Resource = [
          var.training_ecr_repository_arn,
          var.inference_ecr_repository_arn
        ]
      },
      {
        Sid    = "EksDeploy"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster"
        ]
        Resource = "*"
      },
      {
        Sid    = "MLflowTracking"
        Effect = "Allow"
        Action = [
          "sagemaker:CreatePresignedMlflowTrackingServerUrl",
          "sagemaker:GetMlflowTrackingServer"
        ]
        Resource = var.mlflow_tracking_server_arn
      },
      {
        Sid    = "ReadWriteModelAndDataArtifacts"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
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

resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = var.cluster_name
  principal_arn = aws_iam_role.github_actions.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions_admin" {
  cluster_name  = var.cluster_name
  principal_arn = aws_iam_role.github_actions.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.github_actions]
}

# ---------------------------------------------------------------------------
# GitHub Actions — tự động set vars và secrets sau terraform apply
# Provider "github" cần GITHUB_TOKEN env var hoặc token trong providers.tf
# ---------------------------------------------------------------------------

resource "github_actions_variable" "aws_region" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "AWS_REGION"
  value         = var.aws_region
}

resource "github_actions_variable" "aws_role_arn" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "AWS_ROLE_ARN"
  value         = aws_iam_role.github_actions.arn
}

resource "github_actions_variable" "eks_cluster_name" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "EKS_CLUSTER_NAME"
  value         = var.cluster_name
}

resource "github_actions_variable" "inference_ecr_repository_url" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "INFERENCE_ECR_REPOSITORY_URL"
  value         = var.inference_ecr_repository_url
}

resource "github_actions_variable" "training_ecr_repository_url" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "TRAINING_ECR_REPOSITORY_URL"
  value         = var.training_ecr_repository_url
}

resource "github_actions_variable" "inference_service_account_role_arn" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "INFERENCE_SERVICE_ACCOUNT_ROLE_ARN"
  value         = var.inference_service_account_role_arn
}

resource "github_actions_variable" "model_s3_uri" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "MODEL_S3_URI"
  value         = var.model_s3_uri
}

resource "github_actions_variable" "redis_host" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "REDIS_HOST"
  value         = var.redis_host
}

resource "github_actions_variable" "redis_port" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "REDIS_PORT"
  value         = var.redis_port
}

resource "github_actions_secret" "redis_auth_token" {
  repository      = split("/", var.github_repository)[1]
  secret_name     = "REDIS_AUTH_TOKEN"
  plaintext_value = var.redis_auth_token
}

resource "github_actions_secret" "grafana_admin_password" {
  repository      = split("/", var.github_repository)[1]
  secret_name     = "GRAFANA_ADMIN_PASSWORD"
  plaintext_value = var.grafana_admin_password
}

resource "github_actions_variable" "mlflow_tracking_uri" {
  repository    = split("/", var.github_repository)[1]
  variable_name = "MLFLOW_TRACKING_URI"
  value         = var.mlflow_tracking_uri
}
