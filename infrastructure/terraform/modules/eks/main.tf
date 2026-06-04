module "eks" {
    source  = "terraform-aws-modules/eks/aws"
    version = "~> 21.0"
    name               = "${var.project}-${var.env}-eks"
    kubernetes_version = var.cluster_version
    vpc_id     = var.vpc_id
    subnet_ids = var.private_subnet_ids
    endpoint_public_access  = true
    endpoint_private_access = true
    enable_irsa = true
    addons = { 
            coredns = {}, 
        kube-proxy = {}, 
        vpc-cni = {}, 
        aws-ebs-csi-driver = {} 
    }
    eks_managed_node_groups = { 
        default = { 
            name = "${var.project}-${var.env}-default-ng", 
            instance_types = var.node_instance_types, 
            min_size = var.node_min_size, 
            desired_size = var.node_desired_size, 
            max_size = var.node_max_size, 
            capacity_type = "ON_DEMAND" 
        } 
    }
  tags = { Project = var.project, Env = var.env }
}
