# Langfuse LLM Observability Platform
# Provides advanced observability, analytics, and debugging for LLM applications
# Features: trace visualization, prompt management, evaluation, analytics
resource "helm_release" "langfuse" {
  name      = "langfuse"
  chart     = "langfuse"
  namespace = "langfuse"

  repository       = "https://langfuse.github.io/langfuse-k8s"
  create_namespace = true
  timeout          = 900

  values = [
    yamlencode({
      # Langfuse application configuration
      langfuse = {
        salt = {
          value = random_password.langfuse_salt.result
        }
        nextauth = {
          url = "https://langfuse.${var.domain}"
          secret = {
            value = random_password.langfuse_nextauth_secret.result
          }
        }
        encryptionKey = {
          value = random_id.langfuse_encryption_key.hex
        }
        # Headless initialization - auto-create user, org, and project with API keys
        # Note: Using additionalEnv (not extraEnv) as per Helm chart template
        additionalEnv = [
          {
            name  = "LANGFUSE_INIT_ORG_ID"
            value = "dreamfarm-org"
          },
          {
            name  = "LANGFUSE_INIT_ORG_NAME"
            value = "Dreamfarm Organization"
          },
          {
            name  = "LANGFUSE_INIT_PROJECT_ID"
            value = "dreamfarm-project"
          },
          {
            name  = "LANGFUSE_INIT_PROJECT_NAME"
            value = "Dreamfarm AI Project"
          },
          {
            name  = "LANGFUSE_INIT_PROJECT_PUBLIC_KEY"
            value = local.langfuse_public_key
          },
          {
            name  = "LANGFUSE_INIT_PROJECT_SECRET_KEY"
            value = local.langfuse_secret_key
          },
          {
            name  = "LANGFUSE_INIT_USER_EMAIL"
            value = "admin@dreamfarm.local"
          },
          {
            name  = "LANGFUSE_INIT_USER_NAME"
            value = "Dreamfarm Admin"
          },
          {
            name  = "LANGFUSE_INIT_USER_PASSWORD"
            value = random_password.langfuse_admin_password.result
          }
        ]
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "200m"
          }
          limits = {
            memory = "1Gi"
            cpu    = "1000m"
          }
        }
        ingress = {
          enabled   = true
          className = "nginx"
          annotations = {
            "cert-manager.io/cluster-issuer" = "letsencrypt-prod"
          }
          hosts = [
            {
              host = "langfuse.${var.domain}"
              paths = [
                {
                  path     = "/"
                  pathType = "Prefix"
                }
              ]
            }
          ]
          tls = {
            enabled    = true
            secretName = "langfuse-tls"
          }
        }
      }
      # PostgreSQL configuration
      postgresql = {
        deploy = true
        auth = {
          username = "langfuse"
          password = random_password.langfuse_postgres.result
          database = "langfuse"
        }
        primary = {
          persistence = {
            size = "10Gi"
          }
          resources = {
            requests = {
              memory = "256Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "1Gi"
              cpu    = "1000m"
            }
          }
        }
      }
      # ClickHouse configuration
      clickhouse = {
        deploy = true
        auth = {
          password = random_password.langfuse_clickhouse.result
        }
        persistence = {
          size = "20Gi"
        }
        resources = {
          requests = {
            memory = "1Gi"
            cpu    = "500m"
          }
          limits = {
            memory = "4Gi"
            cpu    = "2000m"
          }
        }
        zookeeper = {
          enabled = true
          resources = {
            requests = {
              memory = "256Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "1Gi"
              cpu    = "1000m"
            }
          }
        }
      }
      # Redis configuration
      redis = {
        deploy = true
        auth = {
          password = random_password.langfuse_redis.result
        }
        primary = {
          persistence = {
            size = "5Gi"
          }
          resources = {
            requests = {
              memory = "128Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "500m"
            }
          }
        }
      }
      # S3/MinIO configuration (for blob storage)
      s3 = {
        deploy = true
        auth = {
          rootPassword = random_password.langfuse_minio.result
        }
        persistence = {
          size = "20Gi"
        }
        resources = {
          requests = {
            memory = "512Mi"
            cpu    = "250m"
          }
          limits = {
            memory = "2Gi"
            cpu    = "1000m"
          }
        }
      }
    })
  ]

  depends_on = [
    azapi_resource.aks,
    helm_release.nginx_ingress,
    helm_release.cert_manager
  ]
}

# Random passwords for Langfuse components
resource "random_password" "langfuse_salt" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_nextauth_secret" {
  length  = 32
  special = false
}

resource "random_id" "langfuse_encryption_key" {
  byte_length = 32 # 32 bytes = 64 hex characters
}

resource "random_password" "langfuse_postgres" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_clickhouse" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_redis" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_minio" {
  length  = 32
  special = false
}

# API keys for headless initialization
resource "random_password" "langfuse_public_key" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_secret_key" {
  length  = 32
  special = false
}

resource "random_password" "langfuse_admin_password" {
  length  = 32
  special = false
}

# Local values for API keys with prefixes
locals {
  langfuse_public_key  = "pk-lf-${random_password.langfuse_public_key.result}"
  langfuse_secret_key  = "sk-lf-${random_password.langfuse_secret_key.result}"
  langfuse_auth_header = "Basic ${base64encode("${local.langfuse_public_key}:${local.langfuse_secret_key}")}"
}

# Output Langfuse access information
output "langfuse_url" {
  value       = "https://langfuse.${var.domain}"
  description = "Langfuse UI URL for accessing the observability dashboard"
}

output "langfuse_otlp_endpoint" {
  value       = "http://langfuse-web.langfuse.svc.cluster.local:3000/api/public/otel"
  description = "Langfuse OTLP endpoint for OpenTelemetry collector (internal cluster URL)"
}

output "langfuse_admin_email" {
  value       = "admin@dreamfarm.local"
  description = "Langfuse admin user email for initial login"
}

output "langfuse_admin_password" {
  value       = random_password.langfuse_admin_password.result
  description = "Langfuse admin user password"
  sensitive   = true
}

output "langfuse_public_key" {
  value       = local.langfuse_public_key
  description = "Langfuse project public API key for SDK integration"
  sensitive   = true
}

output "langfuse_secret_key" {
  value       = local.langfuse_secret_key
  description = "Langfuse project secret API key for SDK integration"
  sensitive   = true
}
