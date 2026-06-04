output "vpc_id" {
    value = module.networking.vpc_id
}

output "public_subnet_ids" {
    value = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
    value = module.networking.private_subnet_ids
}

output "eks_nodes_security_group_id" {
    value = module.networking.eks_nodes_security_group_id
}

output "redis_security_group_id" {
    value = module.networking.redis_security_group_id
}

output "alb_security_group_id" {
    value = module.networking.alb_security_group_id
}

output "data_bucket_name" { 
    value = module.data_lake.data_bucket_name 
}

output "model_bucket_name" { 
    value = module.data_lake.model_bucket_name 
}

output "glue_database_name" { 
    value = module.data_lake.glue_database_name 
}

output "eks_cluster_name" { 
    value = module.eks.cluster_name 
}

output "eks_cluster_endpoint" { 
    value = module.eks.cluster_endpoint 
}

output "redis_primary_endpoint_address" { 
    value = module.feature_store.redis_primary_endpoint_address 
}

output "redis_port" { 
    value = module.feature_store.redis_port 
}

output "redis_replication_group_id" { 
    value = module.feature_store.redis_replication_group_id 
}

output "redis_auth_token" {
  value     = module.feature_store.redis_auth_token
  sensitive = true
}

output "training_ecr_repository_url" {
  value = module.training.training_ecr_repository_url
}

output "inference_ecr_repository_url" {
  value = module.training.inference_ecr_repository_url
}

output "sagemaker_execution_role_arn" {
  value = module.training.sagemaker_execution_role_arn
}

output "sagemaker_model_package_group_name" {
  value = module.training.sagemaker_model_package_group_name
}

output "inference_service_account_role_arn" {
  value = module.iam.inference_service_account_role_arn
}

output "inference_namespace" {
  value = module.iam.inference_namespace
}

output "inference_service_account_name" {
  value = module.iam.inference_service_account_name
}

output "github_actions_role_arn" {
  value = module.cicd.github_actions_role_arn
}

output "github_oidc_provider_arn" {
  value = module.cicd.github_oidc_provider_arn
}

output "istio_namespace" {
  value = module.istio.istio_namespace
}

output "istio_inference_namespace" {
  value = module.istio.inference_namespace
}

output "istiod_release_name" {
  value = module.istio.istiod_release_name
}

output "istio_ingressgateway_release_name" {
  value = module.istio.istio_ingressgateway_release_name
}

output "alerts_topic_arn" {
  value = module.monitoring.alerts_topic_arn
}

output "prometheus_release_name" {
  value = module.monitoring.prometheus_release_name
}

output "drift_detector_lambda_name" {
  value = module.monitoring.drift_detector_lambda_name
}

output "mlflow_tracking_server_arn" {
  value = module.training.mlflow_tracking_server_arn
}
