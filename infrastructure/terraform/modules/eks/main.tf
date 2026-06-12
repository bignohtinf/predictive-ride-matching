module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = "${var.project}-${var.env}-eks"
  kubernetes_version = var.cluster_version

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  endpoint_public_access  = true
  endpoint_private_access = true

  authentication_mode                      = "API_AND_CONFIG_MAP"
  enable_cluster_creator_admin_permissions = false
  enable_irsa                              = true

  access_entries = merge(
    # Admin access cho người chạy terraform (cluster creator)
    {
      cluster_creator = {
        principal_arn = data.aws_caller_identity.current.arn
        type          = "STANDARD"

        policy_associations = {
          admin_policy = {
            policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
            access_scope = {
              type = "cluster"
            }
          }
        }
      }
    },
    # Admin access cho các IAM principals khác (nếu khác cluster creator)
    var.local_admin_arn != null && var.local_admin_arn != data.aws_caller_identity.current.arn ? {
      local_admin = {
        principal_arn = var.local_admin_arn
        type          = "STANDARD"

        policy_associations = {
          admin_policy = {
            policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
            access_scope = {
              type = "cluster"
            }
          }
        }
      }
    } : {}
  )
  addons = {
    vpc-cni    = { most_recent = true, resolve_conflicts_on_create = "OVERWRITE", resolve_conflicts_on_update = "OVERWRITE" }
    kube-proxy = { most_recent = true, resolve_conflicts_on_create = "OVERWRITE", resolve_conflicts_on_update = "OVERWRITE" }
    coredns    = { most_recent = true, resolve_conflicts_on_create = "OVERWRITE", resolve_conflicts_on_update = "OVERWRITE" }
  }

  eks_managed_node_groups = var.create_node_groups ? {
    default = {
      name           = "${var.project}-${var.env}-default-ng"
      instance_types = var.node_instance_types
      min_size       = var.node_min_size
      desired_size   = var.node_desired_size
      max_size       = var.node_max_size
      capacity_type  = "ON_DEMAND"
    }
  } : {}

  tags = {
    Project = var.project
    Env     = var.env
  }
}
data "aws_caller_identity" "current" {}

variable "local_admin_arn" {
  description = "Optional: ARN of an additional IAM principal to grant cluster admin. Set null if same as terraform caller."
  type        = string
  default     = null
}
