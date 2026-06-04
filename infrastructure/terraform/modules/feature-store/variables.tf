variable "project" { 
    type = string
}

variable "env" { 
    type = string 
}

variable "private_subnet_ids" { 
    type = list(string) 
}

variable "redis_security_group_id" { 
    type = string 
}

variable "redis_node_type" {
    type = string
    default = "cache.t4g.micro" 
}

variable "redis_engine_version" { 
    type = string
    default = "7.1" 
}

variable "redis_port" { 
    type = number 
    default = 6379 
}
