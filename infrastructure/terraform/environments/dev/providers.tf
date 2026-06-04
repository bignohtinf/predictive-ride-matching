terraform {
    required_version = ">= 1.6.0"

    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
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

# GITHUB_TOKEN env var phải được set khi chạy terraform apply
# export GITHUB_TOKEN=ghp_xxx
provider "github" {
  owner = split("/", var.github_repository)[0]
}

provider "aws" {
    region = var.aws_region
}

data "aws_eks_cluster" "this" { 
    name = module.eks.cluster_name 
}

data "aws_eks_cluster_auth" "this" { 
    name = module.eks.cluster_name 
}

provider "kubernetes" { 
    host = data.aws_eks_cluster.this.endpoint cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data) token = data.aws_eks_cluster_auth.this.token 
}

provider "helm" { 
    kubernetes { 
        host = data.aws_eks_cluster.this.endpoint 
        cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data) 
        token = data.aws_eks_cluster_auth.this.token 
    } 
}
