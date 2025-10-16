# Helm Chart Deployment
#
# This file deploys the demo Helm chart to the AKS cluster.

# Generate random MCP API key for authentication
resource "random_password" "mcp_api_key" {
  length  = 32
  special = false
}

# Generate random Keycloak admin password
resource "random_password" "keycloak_admin" {
  length  = 20
  special = true
}

# Get AKS admin credentials
data "azapi_resource_action" "aks_creds" {
  type        = "Microsoft.ContainerService/managedClusters@2025-07-02-preview"
  resource_id = azapi_resource.aks.id
  action      = "listClusterAdminCredential"
  method      = "POST"

  response_export_values = ["kubeconfigs"]
}

# Get OpenAI API key
data "azurerm_cognitive_account" "ai_services" {
  name                = azurerm_cognitive_account.ai_services.name
  resource_group_name = azurerm_resource_group.main.name
}

locals {
  # The kubeconfig is base64-encoded YAML, we need to decode and parse it
  kubeconfig_raw = base64decode(data.azapi_resource_action.aks_creds.output.kubeconfigs[0].value)
  kubeconfig     = yamldecode(local.kubeconfig_raw)

  # OpenAI configuration - use resource-specific endpoint format
  # Format: https://<resource-name>.openai.azure.com/openai/v1/
  openai_endpoint = "https://${azurerm_cognitive_account.ai_services.name}.openai.azure.com/"
  openai_base_url = "${local.openai_endpoint}openai/v1/"

  # Node resource group follows Azure's naming convention: MC_<rg>_<cluster>_<location>
  node_resource_group = "MC_${azurerm_resource_group.main.name}_${azapi_resource.aks.name}_${azurerm_resource_group.main.location}"
}

# Configure Helm provider to use AKS credentials
provider "helm" {
  kubernetes {
    host                   = local.kubeconfig.clusters[0].cluster.server
    client_certificate     = base64decode(local.kubeconfig.users[0].user["client-certificate-data"])
    client_key             = base64decode(local.kubeconfig.users[0].user["client-key-data"])
    cluster_ca_certificate = base64decode(local.kubeconfig.clusters[0].cluster["certificate-authority-data"])
  }
}
