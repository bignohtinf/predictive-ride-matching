output "aws_load_balancer_controller_role_arn" { 
    value = module.load_balancer_controller_irsa.iam_role_arn 
}

output "aws_load_balancer_controller_release_name" { 
    value = helm_release.aws_load_balancer_controller.name 
}

output "metrics_server_release_name" { 
    value = helm_release.metrics_server.name 
}

output "cluster_autoscaler_role_arn" { 
    value = module.cluster_autoscaler_irsa.iam_role_arn 
}

output "cluster_autoscaler_release_name" { 
    value = helm_release.cluster_autoscaler.name 
}
