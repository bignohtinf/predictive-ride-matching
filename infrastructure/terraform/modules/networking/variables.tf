variable "project" {
    type = string
    default = "predictive-ride-matching"
}

variable "env" {
    type = string
}

variable "vpc_cidr" {
    type = string
    default = "10.0.0.0/16"
}

variable "azs" {
    type = list(string)
}

variable "public_subnet_cidrs" {
    type = list(string)
}

variable "private_subnet_cidrs" {
    type = list(string)
}