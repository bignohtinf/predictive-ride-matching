output "alerts_topic_arn" { 
    value = aws_sns_topic.alerts.arn 
}
output "prometheus_release_name" { 
    value = helm_release.kube_prometheus_stack.name 
}
output "drift_detector_lambda_name" { 
    value = aws_lambda_function.drift_detector.function_name 
}
