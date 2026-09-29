resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.8.1"

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.aws_load_balancer_controller.arn
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  set {
    name  = "vpcId"
    value = module.vpc.vpc_id
  }

  depends_on = [aws_iam_role_policy_attachment.aws_load_balancer_controller]
}

resource "kubernetes_persistent_volume_claim_v1" "uploads" {
  metadata {
    name = "uploads-pvc"
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "gp3"

    resources {
      requests = {
        storage = "1Gi"
      }
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_persistent_volume_claim_v1" "database" {
  metadata {
    name = "db-pvc"
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "gp3"

    resources {
      requests = {
        storage = "1Gi"
      }
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_deployment_v1" "backend" {
  metadata {
    name = "backend"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "backend"
      }
    }

    template {
      metadata {
        labels = {
          app = "backend"
        }
      }

      spec {
        init_container {
          name    = "fix-permissions"
          image   = "busybox:1.36"
          command = ["sh", "-c", "mkdir -p /app/db /app/uploads && chown -R 1000:1000 /app/db /app/uploads"]

          security_context {
            run_as_user = 0
          }

          volume_mount {
            name       = "db-storage"
            mount_path = "/app/db"
          }

          volume_mount {
            name       = "uploads"
            mount_path = "/app/uploads"
          }
        }

        container {
          name  = "backend"
          image = var.backend_image

          port {
            container_port = 8000
          }

          security_context {
            run_as_user  = 1000
            run_as_group = 1000
          }

          volume_mount {
            name       = "uploads"
            mount_path = "/app/uploads"
          }

          volume_mount {
            name       = "db-storage"
            mount_path = "/app/db"
          }
        }

        volume {
          name = "uploads"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.uploads.metadata[0].name
          }
        }

        volume {
          name = "db-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.database.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "backend" {
  metadata {
    name = "backend"
    annotations = {
      "alb.ingress.kubernetes.io/healthcheck-path" = "/availability/all"
    }
  }

  spec {
    selector = {
      app = "backend"
    }

    port {
      port        = 8000
      target_port = 8000
    }
  }
}

resource "kubernetes_deployment_v1" "frontend" {
  metadata {
    name = "frontend"
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "frontend"
      }
    }

    template {
      metadata {
        labels = {
          app = "frontend"
        }
      }

      spec {
        container {
          name  = "frontend"
          image = var.frontend_image

          port {
            container_port = 5000
          }

          env {
            name  = "API_URL"
            value = "http://backend:8000"
          }

          env {
            name  = "PUBLIC_BACKEND_URL"
            value = "http://${var.app_host}"
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name = "frontend"
  }

  spec {
    selector = {
      app = "frontend"
    }

    port {
      port        = 5000
      target_port = 5000
    }
  }
}

resource "kubernetes_ingress_v1" "app" {
  metadata {
    name = "availability-ingress"
    annotations = {
      "kubernetes.io/ingress.class"                       = "alb"
      "alb.ingress.kubernetes.io/scheme"                  = "internet-facing"
      "alb.ingress.kubernetes.io/target-type"             = "ip"
      "alb.ingress.kubernetes.io/listen-ports"            = "[{\"HTTP\":80}]"
    }
  }

  spec {
    ingress_class_name = "alb"

    rule {
      host = var.app_host

      http {
        path {
          path      = "/backend"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service_v1.backend.metadata[0].name

              port {
                number = 8000
              }
            }
          }
        }

        path {
          path      = "/uploads"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service_v1.backend.metadata[0].name

              port {
                number = 8000
              }
            }
          }
        }

        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service_v1.frontend.metadata[0].name

              port {
                number = 5000
              }
            }
          }
        }
      }
    }
  }

  depends_on = [helm_release.aws_load_balancer_controller]
}
