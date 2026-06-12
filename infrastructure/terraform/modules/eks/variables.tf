variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "cluster_version" {
  type    = string
  default = "1.34"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_desired_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 2
}

variable "create_node_groups" {
  description = "Phase 2: tạo node groups sau khi addons đã ACTIVE. Set false ở phase 1."
  type        = bool
  default     = true
}
