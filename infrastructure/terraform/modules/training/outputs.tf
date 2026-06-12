output "training_ecr_repository_url" {
  value = aws_ecr_repository.training.repository_url
}

output "inference_ecr_repository_url" {
  value = aws_ecr_repository.inference.repository_url
}

output "sagemaker_execution_role_arn" {
  value = aws_iam_role.sagemaker_execution.arn
}

output "sagemaker_model_package_group_name" {
  value = aws_sagemaker_model_package_group.crp.model_package_group_name
}

output "training_ecr_repository_arn" {
  value = aws_ecr_repository.training.arn
}

output "inference_ecr_repository_arn" {
  value = aws_ecr_repository.inference.arn
}

output "mlflow_tracking_server_arn" {
  value = aws_sagemaker_mlflow_tracking_server.this.arn
}

output "mlflow_tracking_server_url" {
  value = aws_sagemaker_mlflow_tracking_server.this.tracking_server_url
}