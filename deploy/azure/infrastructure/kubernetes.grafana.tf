# Deploy Grafana observability stack (Tempo + Grafana)
# 
# Grafana Tempo provides distributed tracing backend with OpenTelemetry support.
# Grafana provides visualization and query interface.
# Uses built-in MinIO for demo/local storage (no cloud dependencies).

# Deploy Grafana Tempo (distributed mode with built-in MinIO)
resource "helm_release" "tempo" {
  name             = "tempo"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "tempo-distributed"
  version          = "1.48.1" 
  namespace        = "default"
  create_namespace = false
  timeout          = 900

  values = [
    yamlencode({
      # Built-in MinIO for demo (no cloud storage dependency)
      minio = {
        enabled = true
        mode    = "standalone"
        rootUser     = "grafana-tempo"
        rootPassword = "supersecret"
        buckets = [
          {
            name   = "tempo-traces"
            policy = "none"
            purge  = false
          }
        ]
        persistence = {
          enabled      = true
          storageClass = "managed-csi"
          size         = "10Gi"
        }
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "100m"
          }
          limits = {
            memory = "512Mi"
            cpu    = "500m"
          }
        }
      }

      # Storage configuration pointing to MinIO
      storage = {
        trace = {
          backend = "s3"
          s3 = {
            bucket          = "tempo-traces"
            endpoint        = "tempo-minio:9000"
            access_key      = "grafana-tempo"
            secret_key      = "supersecret"
            insecure        = true
            forcepathstyle  = true
          }
        }
      }

      # Enable OTLP receivers (gRPC and HTTP)
      traces = {
        otlp = {
          grpc = {
            enabled = true
          }
          http = {
            enabled = true
          }
        }
        # Disable other protocols for simplicity
        zipkin = {
          enabled = false
        }
        jaeger = {
          thriftHttp = {
            enabled = false
          }
        }
        opencensus = {
          enabled = false
        }
      }

      # Component resource limits (demo-sized)
      distributor = {
        replicas = 1
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "250m"
          }
          limits = {
            memory = "512Mi"
            cpu    = "500m"
          }
        }
        # Init container to create MinIO bucket before Tempo starts
        initContainers = [
          {
            name  = "create-bucket"
            image = "minio/mc:latest"
            command = ["/bin/sh", "-c"]
            args = [
              "until mc alias set tempo http://tempo-minio:9000 grafana-tempo supersecret; do echo 'Waiting for MinIO...'; sleep 2; done && mc mb --ignore-existing tempo/tempo-traces && echo 'Bucket ready'"
            ]
          }
        ]
      }

      ingester = {
        replicas = 1
        resources = {
          requests = {
            memory = "512Mi"
            cpu    = "250m"
          }
          limits = {
            memory = "1Gi"
            cpu    = "500m"
          }
        }
        persistence = {
          enabled      = true
          storageClass = "managed-csi"
          size         = "10Gi"
        }
        # Set replication factor to 1 for demo (default is 3)
        config = {
          replication_factor = 1
        }
      }

      compactor = {
        replicas = 1
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "250m"
          }
          limits = {
            memory = "512Mi"
            cpu    = "500m"
          }
        }
      }

      querier = {
        replicas = 1
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "250m"
          }
          limits = {
            memory = "512Mi"
            cpu    = "500m"
          }
        }
      }

      queryFrontend = {
        replicas = 1
        resources = {
          requests = {
            memory = "128Mi"
            cpu    = "100m"
          }
          limits = {
            memory = "256Mi"
            cpu    = "200m"
          }
        }
      }

      metricsGenerator = {
        enabled  = true
        replicas = 1
        resources = {
          requests = {
            memory = "512Mi"
            cpu    = "250m"
          }
          limits = {
            memory = "1Gi"
            cpu    = "500m"
          }
        }
        # Enable local-blocks processor for TraceQL metrics queries
        config = {
          processor = {
            local_blocks = {
              flush_to_storage = false  # Keep in-memory only for demo
              max_live_traces  = 10000
              max_block_duration = "5m"
            }
          }
          registry = {
            collection_interval = "15s"
          }
        }
      }
    })
  ]

  depends_on = [
    azapi_resource.aks,
    helm_release.nginx_ingress
  ]
}

# Generate random password for Grafana admin
resource "random_password" "grafana_admin" {
  length  = 16
  special = true
}

# Deploy Grafana for visualization
resource "helm_release" "grafana" {
  name             = "grafana"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "grafana"
  version          = "10.1.1" # Latest stable version
  namespace        = "default"
  create_namespace = false
  timeout          = 600

  values = [
    yamlencode({
      # Admin credentials (randomly generated)
      adminUser     = "admin"
      adminPassword = random_password.grafana_admin.result

      # Persistence for dashboards
      persistence = {
        enabled      = true
        storageClass = "managed-csi"
        size         = "5Gi"
      }

      # Resource limits
      resources = {
        requests = {
          memory = "256Mi"
          cpu    = "100m"
        }
        limits = {
          memory = "512Mi"
          cpu    = "200m"
        }
      }

      # Datasources - pre-configure Tempo
      datasources = {
        "datasources.yaml" = {
          apiVersion = 1
          datasources = [
            {
              name   = "Tempo"
              type   = "tempo"
              access = "proxy"
              url    = "http://tempo-query-frontend:3200"
              uid    = "tempo"
              jsonData = {
                tracesToLogsV2 = {
                  customQuery = false
                  datasourceUid = null
                }
                serviceMap = {
                  datasourceUid = null
                }
                nodeGraph = {
                  enabled = true
                }
              }
            }
          ]
        }
      }

      # Service configuration
      service = {
        type = "ClusterIP"
        port = 80
      }

      # Ingress configuration
      ingress = {
        enabled = true
        ingressClassName = "nginx"
        annotations = {
          "cert-manager.io/cluster-issuer" = "letsencrypt-prod"
        }
        hosts = ["grafana.${var.domain}"]
        tls = [
          {
            secretName = "grafana-tls"
            hosts      = ["grafana.${var.domain}"]
          }
        ]
      }

      # Grafana configuration
      "grafana.ini" = {
        server = {
          root_url = "https://grafana.${var.domain}"
          domain   = "grafana.${var.domain}"
        }
        "auth.anonymous" = {
          enabled  = false  # Disable anonymous access for production
        }
      }
    })
  ]

  depends_on = [
    azapi_resource.aks,
    helm_release.nginx_ingress,
    helm_release.tempo
  ]
}

# Outputs for verification
output "helm_tempo_status" {
  description = "Status of the Tempo Helm release"
  value = {
    name      = helm_release.tempo.name
    namespace = helm_release.tempo.namespace
    version   = helm_release.tempo.version
    status    = helm_release.tempo.status
  }
}

output "helm_grafana_status" {
  description = "Status of the Grafana Helm release"
  value = {
    name      = helm_release.grafana.name
    namespace = helm_release.grafana.namespace
    version   = helm_release.grafana.version
    status    = helm_release.grafana.status
  }
}

output "tempo_services" {
  description = "Tempo service endpoints for OpenTelemetry Collector"
  value = {
    otlp_grpc_endpoint = "tempo-distributed-distributor.default.svc.cluster.local:4317"
    otlp_http_endpoint = "tempo-distributed-distributor.default.svc.cluster.local:4318"
    query_frontend_url = "http://tempo-distributed-query-frontend.default.svc.cluster.local:3200"
  }
}

output "grafana_access" {
  description = "Grafana access information"
  value = {
    url            = "https://grafana.${var.domain}"
    admin_user     = "admin"
    admin_password = random_password.grafana_admin.result
  }
  sensitive = true
}
