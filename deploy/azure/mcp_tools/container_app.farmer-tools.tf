resource "azapi_resource" "farmer_tools" {
  type      = "Microsoft.App/containerApps@2025-02-02-preview"
  name      = "ca-mcp-farmer-tools"
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
            name  = "farmer-tools-api-key"
            value = var.farmer_tools_api_key
          }
        ]
        ingress = {
          external   = true
          targetPort = 8012
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
          minReplicas     = var.farmer_tools_min_replicas
          maxReplicas     = 1
          cooldownPeriod  = 3600
          pollingInterval = 30
        }
        containers = [
          {
            name  = "farmer-tools"
            image = var.farmer_tools_image
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
                value = "8012"
              },
              {
                name  = "MCP_CORS_ORIGINS"
                value = "*"
              },
              {
                name      = "MCP_API_KEY"
                secretRef = "farmer-tools-api-key"
              },
              {
                name  = "LOG_LEVEL"
                value = "INFO"
              }
            ]
          }
        ]
      }
    }
  }

  response_export_values = ["properties.configuration.ingress.fqdn"]
}

output "farmer_tools_url" {
  description = "Public URL for the farmer tools MCP server"
  value       = "https://${azapi_resource.farmer_tools.output.properties.configuration.ingress.fqdn}"
}
