variable "aws_region" {
    type = string
    default = "ap-southeast-1"
}

variable "project" {
    type = string
    default = "crp"
}

variable "env" {
    type = string
    default = "dev"
}

variable "github_repository" {
  description = "GitHub repository allowed to assume CI/CD role, format: owner/repo"
  type        = string
  default     = "bignohtinf/predictive-ride-matching"
}

variable "github_branch" {
  description = "Branch allowed to assume CI/CD role"
  type        = string
  default     = "main"
}

variable "grafana_admin_password" {
  description = "Grafana admin password — pass via TF_VAR_grafana_admin_password, không commit vào git"
  type        = string
  sensitive   = true
}

variable "create_node_groups" {
  description = "Tạo EKS managed node groups. Set false chỉ khi cần deploy cluster trống (phase 1 bootstrap)."
  type        = bool
  default     = true
}

variable "local_admin_arn" {
  description = "Optional: ARN of additional IAM principal for cluster admin. Null = chỉ dùng caller identity."
  type        = string
  default     = null
}