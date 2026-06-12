resource "random_password" "redis_auth_token" {
    length  = 32
    special = false
}

resource "aws_elasticache_subnet_group" "redis" {
    name       = "${var.project}-${var.env}-redis-subnet-group"
    subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "redis" {
    replication_group_id = "${var.project}-${var.env}-redis"
    description          = "Online feature store Redis for ${var.project}-${var.env}"
    engine         = "redis"
    engine_version = var.redis_engine_version
    node_type      = var.redis_node_type
    port           = var.redis_port
    parameter_group_name       = "default.redis7"
    subnet_group_name          = aws_elasticache_subnet_group.redis.name
    security_group_ids         = [var.redis_security_group_id]
    num_cache_clusters         = 1
    automatic_failover_enabled = false
    multi_az_enabled           = false
    at_rest_encryption_enabled = true
    transit_encryption_enabled = true
    auth_token                 = random_password.redis_auth_token.result
    apply_immediately = true

    tags = {
        Project = var.project
        Env     = var.env
        Purpose = "online-feature-store"
  }
}
