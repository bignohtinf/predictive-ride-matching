resource "kubernetes_namespace" "istio_system" {
  metadata {
    name = var.istio_namespace
  }
}

resource "helm_release" "istio_base" {
  name       = "istio-base"
  namespace  = kubernetes_namespace.istio_system.metadata[0].name
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "base"
  version    = var.istio_chart_version

  wait = true
}

resource "helm_release" "istiod" {
  name       = "istiod"
  namespace  = kubernetes_namespace.istio_system.metadata[0].name
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "istiod"
  version    = var.istio_chart_version

  wait = true

  depends_on = [
    helm_release.istio_base
  ]
}

resource "helm_release" "istio_ingressgateway" {
  name       = "istio-ingressgateway"
  namespace  = kubernetes_namespace.istio_system.metadata[0].name
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "gateway"
  version    = var.istio_chart_version

  wait             = false  # LoadBalancer provisioning is async — don't block apply
  timeout          = 600
  replace          = true   # Force replace failed release
  cleanup_on_fail  = true   # Auto-cleanup on failure to avoid stuck state

  set {
    name  = "service.type"
    value = "LoadBalancer"
  }
  set {
    name  = "service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-type"
    value = "external"
  }
  set {
    name  = "service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-scheme"
    value = "internal"
  }

  depends_on = [
    helm_release.istiod
  ]
}

resource "kubernetes_namespace" "inference" {
  metadata {
    name = var.inference_namespace

    labels = var.enable_sidecar_injection ? {
      "istio-injection" = "enabled"
    } : {}
  }
}
