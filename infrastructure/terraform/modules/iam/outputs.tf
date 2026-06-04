output "inference_service_account_role_arn" {
  value = module.inference_irsa.iam_role_arn
}

output "inference_namespace" {
  value = var.namespace
}

output "inference_service_account_name" {
  value = var.service_account_name
}
