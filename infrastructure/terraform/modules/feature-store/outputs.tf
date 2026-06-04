output "redis_primary_endpoint_address" { 
    value = aws_elasticache_replication_group.redis.primary_endpoint_address 
}

output "redis_port" { 
    value = aws_elasticache_replication_group.redis.port 
}

output "redis_replication_group_id" { 
    value = aws_elasticache_replication_group.redis.replication_group_id 
}

output "redis_auth_token" { 
    value = random_password.redis_auth_token.result 
    sensitive = true 
}
