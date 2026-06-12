terraform {
    required_version = ">= 1.6.0"

    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 6.0"
        }

        helm = { 
            source = "hashicorp/helm",
            version = "~> 2.17" 
        }
        
        kubernetes = { 
            source = "hashicorp/kubernetes",
            version = "~> 2.35"
        }
        
        random = {
            source  = "hashicorp/random"
            version = "~> 3.6"
        }

        github = {
            source  = "integrations/github"
            version = "~> 6.0"
        }
    }
}

provider "github" {
  owner = split("/", var.github_repository)[0]
}

provider "aws" {
    region = var.aws_region
}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    command     = "aws"
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
      command     = "aws"
    }
  }
}
