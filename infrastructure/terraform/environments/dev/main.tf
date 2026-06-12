module "networking" {
    source = "../../modules/networking"

    project = var.project
    env = var.env

    vpc_cidr = "10.0.0.0/16"

    azs = [
        "ap-southeast-1a",
        "ap-southeast-1b"
    ]

    public_subnet_cidrs = [
        "10.0.1.0/24",
        "10.0.2.0/24"
    ]

    private_subnet_cidrs = [
        "10.0.11.0/24",
        "10.0.12.0/24"
    ]

    # Required để tag subnets đúng cách cho EKS node discovery
    cluster_name = "${var.project}-${var.env}-eks"
}

module "data_lake" {
  source = "../../modules/data-lake"
  project = var.project
  env     = var.env
}

module "eks" {
  source = "../../modules/eks"
  project = var.project
  env     = var.env
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  cluster_version = "1.33"  # TODO: upgrade tiếp lên 1.34 sau khi 1.33 ACTIVE
  node_instance_types = ["t3.medium"]
  node_min_size = 1
  node_desired_size = 1
  node_max_size = 2
  create_node_groups = var.create_node_groups
  # local_admin_arn auto-detected from caller identity.
  # Set explicitly only if you need a DIFFERENT user to also have admin access.
  # Example: local_admin_arn = "arn:aws:iam::516909141871:role/some-other-role"
}

module "eks_addons" {
  source = "../../modules/eks-addons"
  project = var.project
  env = var.env
  aws_region = var.aws_region
  cluster_name = module.eks.cluster_name
  vpc_id = module.networking.vpc_id
  oidc_provider_arn = module.eks.oidc_provider_arn
  depends_on = [module.eks]
}


module "feature_store" {
  source = "../../modules/feature-store"
  project = var.project
  env     = var.env
  private_subnet_ids       = module.networking.private_subnet_ids
  redis_security_group_id  = module.networking.redis_security_group_id
  redis_node_type          = "cache.t4g.micro"
  redis_engine_version     = "7.1"
}

module "training" {
  source = "../../modules/training"

  project = var.project
  env     = var.env

  data_bucket_name  = module.data_lake.data_bucket_name
  model_bucket_name = module.data_lake.model_bucket_name
}

module "iam" {
  source = "../../modules/iam"

  project = var.project
  env     = var.env

  oidc_provider_arn = module.eks.oidc_provider_arn
  model_bucket_name = module.data_lake.model_bucket_name

  namespace            = "crp-inference"
  service_account_name = "crp-inference"

  depends_on = [module.eks]
}

module "cicd" {
  source = "../../modules/cicd"

  project           = var.project
  env               = var.env
  aws_region        = var.aws_region
  github_repository = var.github_repository
  github_branch     = var.github_branch

  cluster_name = module.eks.cluster_name

  training_ecr_repository_arn  = module.training.training_ecr_repository_arn
  inference_ecr_repository_arn = module.training.inference_ecr_repository_arn

  data_bucket_name  = module.data_lake.data_bucket_name
  model_bucket_name = module.data_lake.model_bucket_name

  # GitHub Actions vars/secrets — tự động set sau terraform apply
  inference_ecr_repository_url       = module.training.inference_ecr_repository_url
  training_ecr_repository_url        = module.training.training_ecr_repository_url
  inference_service_account_role_arn = module.iam.inference_service_account_role_arn
  model_s3_uri                       = "s3://${module.data_lake.model_bucket_name}/models/champion/model.tar.gz"
  redis_host                         = module.feature_store.redis_primary_endpoint_address
  redis_port                         = tostring(module.feature_store.redis_port)
  redis_auth_token                   = module.feature_store.redis_auth_token
  grafana_admin_password             = var.grafana_admin_password
  mlflow_tracking_server_arn         = module.training.mlflow_tracking_server_arn
  mlflow_tracking_uri                = module.training.mlflow_tracking_server_url

  depends_on = [
    module.eks,
    module.training,
    module.iam,
    module.feature_store
  ]
}

module "istio" {
  source = "../../modules/istio"

  project = var.project
  env     = var.env

  istio_namespace          = "istio-system"
  inference_namespace      = "crp-inference"
  istio_chart_version      = "1.27.0"
  enable_sidecar_injection = true

  depends_on = [
    module.eks,
    module.eks_addons
  ]
}

module "monitoring" {
  source = "../../modules/monitoring"

  project    = var.project
  env        = var.env
  aws_region = var.aws_region

  cluster_name               = module.eks.cluster_name
  redis_replication_group_id = module.feature_store.redis_replication_group_id

  enable_email_alerts    = false
  alert_email            = "thongphil18.com"
  grafana_admin_password = var.grafana_admin_password

  depends_on = [
    module.eks,
    module.eks_addons,
    module.feature_store
  ]
}

