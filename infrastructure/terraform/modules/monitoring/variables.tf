variable "project" {
  type = string
}
variable "env" { 
    type = string 
}
variable "aws_region" { 
    type = string 
}
variable "cluster_name" { 
    type = string 
}
variable "redis_replication_group_id" { 
    type = string 
}
variable "alert_email" { 
    type = string 
}
variable "enable_email_alerts" {
  type    = bool
  default = false
}

variable "grafana_admin_password" {
  type      = string
  sensitive = true
}
