variable "project" {
  type = string
}

variable "env" { 
    type = string
}

variable "oidc_provider_arn" { 
    type = string
}

variable "model_bucket_name" { 
    type = string
}

variable "namespace" { 
    type = string 
    default = "crp-inference"
}

variable "service_account_name" { 
    type = string 
    default = "crp-inference" 
}
