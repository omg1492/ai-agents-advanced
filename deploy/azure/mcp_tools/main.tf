resource "azapi_resource" "main" {
  type      = "Microsoft.Resources/resourceGroups@2021-04-01"
  name      = var.resource_group_name
  location  = var.location
  parent_id = "/subscriptions/673af34d-6b28-41dc-bc7b-f507418045e6"
}

resource "azapi_resource" "log_analytics" {
  type      = "Microsoft.OperationalInsights/workspaces@2022-10-01"
  name      = "law-${var.resource_group_name}"
  location  = var.location
  parent_id = azapi_resource.main.id

  body = {
    properties = {
      sku = {
        name = "PerGB2018"
      }
      retentionInDays = 30
    }
  }

  response_export_values = ["properties.customerId"]
}

resource "azapi_resource_action" "log_analytics_keys" {
  type        = "Microsoft.OperationalInsights/workspaces@2022-10-01"
  resource_id = azapi_resource.log_analytics.id
  action      = "listKeys"
  method      = "POST"

  response_export_values = ["primarySharedKey"]
}