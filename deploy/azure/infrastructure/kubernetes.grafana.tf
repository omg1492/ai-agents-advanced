# Deploy Grafana observability stack (Loki + Prometheus + Tempo + Grafana)
# 
# Complete LGTM Stack:
# - Loki: Log aggregation
# - Grafana: Visualization
# - Tempo: Distributed tracing
# - Mimir/Prometheus: Metrics
#
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
        # Use unique ServiceAccount name to avoid conflict with Loki MinIO
        serviceAccount = {
          create = true
          name   = "tempo-minio-sa"
        }
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

# Deploy Loki (with built-in MinIO for demo storage)
resource "helm_release" "loki" {
  name             = "loki"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "loki"
  version          = "6.43.0"  # Latest stable Loki 3.x with OTLP support (Oct 2025)
  namespace        = "default"
  create_namespace = false
  timeout          = 900

  values = [
    yamlencode({
      # Deployment mode: SingleBinary for demo (simple, all-in-one)
      deploymentMode = "SingleBinary"
      
      # Explicitly disable simpleScalable components to avoid validation error
      read = {
        replicas = 0
      }
      write = {
        replicas = 0
      }
      backend = {
        replicas = 0
      }

      loki = {
        # Auth disabled for internal cluster use
        auth_enabled = false

        # Common config
        commonConfig = {
          replication_factor = 1  # Single replica for demo
        }

        # Storage configuration using MinIO
        storage = {
          type = "s3"
          s3 = {
            endpoint        = "loki-minio:9000"
            bucketNames = {
              chunks = "loki-chunks"
              ruler  = "loki-ruler"
            }
            accessKeyId     = "grafana-loki"
            secretAccessKey = "supersecret"
            s3ForcePathStyle = true
            insecure        = true
          }
        }

        # Schema configuration
        schemaConfig = {
          configs = [
            {
              from   = "2024-01-01"
              store  = "tsdb"
              object_store = "s3"
              schema = "v13"
              index = {
                prefix = "index_"
                period = "24h"
              }
            }
          ]
        }

        # Limits configuration
        limits_config = {
          retention_period           = "168h"  # 7 days retention for demo
          max_query_series           = 5000
          max_query_parallelism      = 32
        }

        # Query range config
        query_range = {
          results_cache = {
            cache = {
              enable_fifocache = true
              fifocache = {
                max_size_items = 1024
                ttl            = "24h"
              }
            }
          }
        }
      }

      # SingleBinary component configuration
      singleBinary = {
        replicas = 1
        resources = {
          requests = {
            cpu    = "250m"
            memory = "512Mi"
          }
          limits = {
            cpu    = "500m"
            memory = "1Gi"
          }
        }
        persistence = {
          enabled      = true
          storageClass = "managed-csi"
          size         = "10Gi"
        }
        # Extra config to enable OTLP receiver
        extraArgs = [
          "-config.expand-env=true"
        ]
      }

      # Built-in MinIO for demo storage (namespaced to avoid conflicts with Tempo MinIO)
      minio = {
        enabled = true
        mode    = "standalone"
        rootUser     = "grafana-loki"
        rootPassword = "supersecret"
        # Use unique ServiceAccount name to avoid conflict with Tempo MinIO
        serviceAccount = {
          create = true
          name   = "loki-minio-sa"
        }
        buckets = [
          {
            name   = "loki-chunks"
            policy = "none"
            purge  = false
          },
          {
            name   = "loki-ruler"
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

      # Gateway disabled (using SingleBinary)
      gateway = {
        enabled = false
      }

      # Monitoring disabled for demo
      monitoring = {
        selfMonitoring = {
          enabled = false
        }
        lokiCanary = {
          enabled = false
        }
      }

      # Test disabled
      test = {
        enabled = false
      }
    })
  ]

  depends_on = [
    azapi_resource.aks,
    helm_release.nginx_ingress
  ]
}

# Deploy Prometheus (kube-prometheus-stack for complete monitoring)
resource "helm_release" "prometheus" {
  name             = "prometheus"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  version          = "78.2.1"  # Latest stable version (Oct 2025)
  namespace        = "default"
  create_namespace = false
  timeout          = 900

  values = [
    yamlencode({
      # Prometheus configuration
      prometheus = {
        prometheusSpec = {
          replicas = 1  # Single replica for demo
          retention = "7d"  # 7 days retention
          retentionSize = "8GB"

          # Storage configuration
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                storageClassName = "managed-csi"
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "10Gi"
                  }
                }
              }
            }
          }

          # Resource limits
          resources = {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }

          # Enable remote write receiver for OTel Collector
          enableRemoteWriteReceiver = true

          # ServiceMonitor selector (monitor all in default namespace)
          serviceMonitorSelectorNilUsesHelmValues = false
          podMonitorSelectorNilUsesHelmValues     = false
          ruleSelectorNilUsesHelmValues           = false
        }
      }

      # Alertmanager - minimal for demo
      alertmanager = {
        enabled = false  # Disabled for demo simplicity
      }

      # Grafana disabled (we deploy separately)
      grafana = {
        enabled = false
      }

      # Kube-state-metrics for cluster monitoring
      kubeStateMetrics = {
        enabled = true
      }

      # Node exporter for node metrics
      nodeExporter = {
        enabled = true
      }

      # Prometheus operator
      prometheusOperator = {
        resources = {
          requests = {
            cpu    = "100m"
            memory = "128Mi"
          }
          limits = {
            cpu    = "200m"
            memory = "256Mi"
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

      # Datasources - pre-configure Tempo, Loki, and Prometheus
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
                  datasourceUid = "loki"
                  customQuery   = true
                  query         = "{service_name=\"$${__span.tags[\"service.name\"]}\"} |~ \"$${__span.traceId}\""
                }
                tracesToMetrics = {
                  datasourceUid = "prometheus"
                  tags = [
                    { key = "service.name", value = "service_name" }
                  ]
                }
                serviceMap = {
                  datasourceUid = "prometheus"
                }
                nodeGraph = {
                  enabled = true
                }
              }
            },
            {
              name   = "Loki"
              type   = "loki"
              access = "proxy"
              url    = "http://loki:3100"
              uid    = "loki"
              jsonData = {
                maxLines = 1000
                derivedFields = [
                  {
                    datasourceUid = "tempo"
                    matcherRegex  = "trace_id[=:]\"?(\\w+)"
                    name          = "TraceID"
                    url           = "$${__value.raw}"
                  }
                ]
              }
            },
            {
              name   = "Prometheus"
              type   = "prometheus"
              access = "proxy"
              url    = "http://prometheus-kube-prometheus-prometheus:9090"
              uid    = "prometheus"
              jsonData = {
                timeInterval = "30s"
                exemplarTraceIdDestinations = [
                  {
                    datasourceUid = "tempo"
                    name          = "trace_id"
                  }
                ]
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
    helm_release.tempo,
    helm_release.loki,
    helm_release.prometheus
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

output "helm_loki_status" {
  description = "Status of the Loki Helm release"
  value = {
    name      = helm_release.loki.name
    namespace = helm_release.loki.namespace
    version   = helm_release.loki.version
    status    = helm_release.loki.status
  }
}

output "helm_prometheus_status" {
  description = "Status of the Prometheus Helm release"
  value = {
    name      = helm_release.prometheus.name
    namespace = helm_release.prometheus.namespace
    version   = helm_release.prometheus.version
    status    = helm_release.prometheus.status
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

output "loki_services" {
  description = "Loki service endpoints for OpenTelemetry Collector"
  value = {
    otlp_grpc_endpoint = "loki:4317"
    otlp_http_endpoint = "loki:4318"
    query_url          = "http://loki:3100"
  }
}

output "prometheus_services" {
  description = "Prometheus service endpoints for OpenTelemetry Collector"
  value = {
    remote_write_url = "http://prometheus-kube-prometheus-prometheus:9090/api/v1/write"
    query_url        = "http://prometheus-kube-prometheus-prometheus:9090"
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

output "observability_stack_summary" {
  description = "Summary of deployed observability components"
  value = {
    tempo      = "Traces: tempo-distributed-distributor.default.svc.cluster.local:4317"
    loki       = "Logs: loki.default.svc.cluster.local:4318 (OTLP HTTP)"
    prometheus = "Metrics: prometheus-kube-prometheus-prometheus.default.svc.cluster.local:9090"
    grafana    = "Dashboards: https://grafana.${var.domain}"
  }
}
