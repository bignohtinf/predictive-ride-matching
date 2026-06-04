resource "aws_sns_topic" "alerts" {
  name = "${var.project}-${var.env}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.enable_email_alerts ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "helm_release" "kube_prometheus_stack" {
  name             = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "75.15.1"

  values = [yamlencode({
    grafana = {
      adminPassword = var.grafana_admin_password
      service = { type = "ClusterIP" }
    }
    prometheus = {
      prometheusSpec = {
        retention = "15d"
        serviceMonitorSelectorNilUsesHelmValues = false
        podMonitorSelectorNilUsesHelmValues     = false
      }
    }
  })]
}

resource "aws_cloudwatch_metric_alarm" "redis_cpu_high" {
  alarm_name          = "${var.project}-${var.env}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Redis CPU is above 80% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ReplicationGroupId = var.redis_replication_group_id
  }
}

resource "aws_cloudwatch_metric_alarm" "redis_memory_high" {
  alarm_name          = "${var.project}-${var.env}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Redis memory usage is above 80% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ReplicationGroupId = var.redis_replication_group_id
  }
}

resource "aws_iam_role" "drift_detector" {
  name = "${var.project}-${var.env}-drift-detector-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "drift_detector" {
  name = "${var.project}-${var.env}-drift-detector-policy"
  role = aws_iam_role.drift_detector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = aws_sns_topic.alerts.arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "drift_detector_schedule" {
  name                = "${var.project}-${var.env}-drift-detector-schedule"
  description         = "Run drift detector every 6 hours"
  schedule_expression = "rate(6 hours)"
}

resource "aws_cloudwatch_event_target" "drift_detector" {
  rule      = aws_cloudwatch_event_rule.drift_detector_schedule.name
  target_id = "drift-detector"
  arn       = aws_lambda_function.drift_detector.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.drift_detector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.drift_detector_schedule.arn
}

data "archive_file" "drift_detector" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambda/drift-detector"
  output_path = "${path.module}/drift-detector.zip"
}

resource "aws_lambda_function" "drift_detector" {
  function_name    = "${var.project}-${var.env}-drift-detector"
  role             = aws_iam_role.drift_detector.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.drift_detector.output_path
  source_code_hash = data.archive_file.drift_detector.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      PROJECT   = var.project
      ENV       = var.env
      SNS_TOPIC = aws_sns_topic.alerts.arn
    }
  }
}
