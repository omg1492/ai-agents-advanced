resource "azapi_resource" "viz_gen" {
  type      = "Microsoft.App/containerApps@2025-02-02-preview"
  name      = "ca-mcp-viz-gen"
  location  = var.location
  parent_id = azapi_resource.main.id

  schema_validation_enabled = true

  body = {
    properties = {
      managedEnvironmentId = azapi_resource.container_app_environment.id
      configuration = {
        activeRevisionsMode = "Single"
        secrets = [
          {
            name  = "viz-gen-api-key"
            value = var.viz_gen_api_key
          },
          {
            name  = "viz-gen-openai-api-key"
            value = var.viz_gen_openai_api_key
          }
        ]
        ingress = {
          external   = true
          targetPort = 5003
          transport  = "auto"
          traffic = [
            {
              latestRevision = true
              weight         = 100
            }
          ]
        }
      }
      template = {
        scale = {
          minReplicas     = var.viz_gen_min_replicas
          maxReplicas     = 1
          cooldownPeriod  = 3600
          pollingInterval = 30
        }
        containers = [
          {
            name  = "viz-gen"
            image = var.viz_gen_image
            resources = {
              cpu    = 0.5
              memory = "1Gi"
            }
            env = [
              {
                name  = "HOST"
                value = "0.0.0.0"
              },
              {
                name  = "PORT"
                value = "5003"
              },
              {
                name  = "MCP_CORS_ORIGINS"
                value = "*"
              },
              {
                name      = "MCP_API_KEY"
                secretRef = "viz-gen-api-key"
              },
              {
                name      = "OPENAI_API_KEY"
                secretRef = "viz-gen-openai-api-key"
              },
              {
                name  = "OPENAI_MODEL"
                value = var.viz_gen_openai_model
              },
              {
                name  = "REASONING_EFFORT"
                value = "low"
              },
              {
                name  = "OPENAI_BASE_URL"
                value = var.viz_gen_openai_base_url
              },
              {
                name  = "OPENAI_API_VERSION"
                value = var.viz_gen_openai_api_version
              },
              {
                name  = "LOG_LEVEL"
                value = "INFO"
              },
              {
                name  = "PYTHONUNBUFFERED"
                value = "1"
              }
            ]
          }
        ]
      }
    }
  }

  response_export_values = ["properties.configuration.ingress.fqdn"]
}

output "viz_gen_url" {
  description = "Public URL for the visualization generator MCP server"
  value       = "https://${azapi_resource.viz_gen.output.properties.configuration.ingress.fqdn}"
}
