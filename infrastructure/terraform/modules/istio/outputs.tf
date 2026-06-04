output "istio_namespace" {
  value = kubernetes_namespace.istio_system.metadata[0].name
}

output "inference_namespace" {
  value = kubernetes_namespace.inference.metadata[0].name
}

output "istio_base_release_name" {
  value = helm_release.istio_base.name
}

output "istiod_release_name" {
  value = helm_release.istiod.name
}

output "istio_ingressgateway_release_name" {
  value = helm_release.istio_ingressgateway.name
}
