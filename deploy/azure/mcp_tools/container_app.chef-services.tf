resource "azapi_resource" "chef_services" {
  type      = "Microsoft.App/containerApps@2025-02-02-preview"
  name      = "ca-mcp-chef-services"
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
            name  = "chef-services-api-key"
            value = var.chef_services_api_key
          }
        ]
        ingress = {
          external   = true
          targetPort = 8013
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
          minReplicas     = var.chef_services_min_replicas
          maxReplicas     = 1
          cooldownPeriod  = 3600
          pollingInterval = 30
        }
        containers = [
          {
            name  = "chef-services"
            image = var.chef_services_image
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
                value = "8013"
              },
              {
                name  = "MCP_CORS_ORIGINS"
                value = "*"
              },
              {
                name      = "MCP_API_KEY"
                secretRef = "chef-services-api-key"
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

output "chef_services_url" {
  description = "Public URL for the chef services MCP server"
  value       = "https://${azapi_resource.chef_services.output.properties.configuration.ingress.fqdn}"
}
