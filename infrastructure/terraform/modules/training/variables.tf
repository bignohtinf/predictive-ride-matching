variable "project" {
  type = string
}

variable "env" {
    type = string
}

variable "data_bucket_name" {
    type = string
}

variable "model_bucket_name" {
    type = string
}

variable "ecr_image_keep_count" {
    type    = number
    default = 10
}