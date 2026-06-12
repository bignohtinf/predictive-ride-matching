variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the CI/CD role, format: owner/repo"
  type        = string
}

variable "github_branch" {
  description = "Branch allowed to assume the CI/CD role"
  type        = string
  default     = "main"
}

variable "aws_region" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "training_ecr_repository_arn" {
  type = string
}

variable "inference_ecr_repository_arn" {
  type = string
}

variable "model_bucket_name" {
  type = string
}

variable "data_bucket_name" {
  type = string
}

variable "inference_ecr_repository_url" {
  type = string
}

variable "training_ecr_repository_url" {
  type = string
}

variable "inference_service_account_role_arn" {
  type = string
}

variable "model_s3_uri" {
  type = string
}

variable "redis_host" {
  type = string
}

variable "redis_port" {
  type = string
}

variable "redis_auth_token" {
  type      = string
  sensitive = true
}

variable "grafana_admin_password" {
  type      = string
  sensitive = true
}

variable "mlflow_tracking_server_arn" {
  type = string
}

variable "mlflow_tracking_uri" {
  type = string
}

variable "deploy_namespaces" {
  description = "Kubernetes namespaces that GitHub Actions can deploy to"
  type        = list(string)
  default     = ["crp-inference"]
}
