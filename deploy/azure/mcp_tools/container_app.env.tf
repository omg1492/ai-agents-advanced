resource "azapi_resource" "container_app_environment" {
  type      = "Microsoft.App/managedEnvironments@2024-03-01"
  name      = "cae-mcp-tools"
  location  = var.location
  parent_id = azapi_resource.main.id

  body = {
    properties = {
      appLogsConfiguration = {
        destination = "log-analytics"
        logAnalyticsConfiguration = {
          customerId = azapi_resource.log_analytics.output.properties.customerId
          sharedKey  = azapi_resource_action.log_analytics_keys.output.primarySharedKey
        }
      }
    }
  }
}