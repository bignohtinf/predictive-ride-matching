variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "istio_namespace" {
  type    = string
  default = "istio-system"
}

variable "inference_namespace" {
  type    = string
  default = "crp-inference"
}

variable "istio_chart_version" {
  type    = string
  default = "1.27.0"
}

variable "enable_sidecar_injection" {
  type    = bool
  default = true
}
