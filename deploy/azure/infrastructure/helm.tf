# Helm Chart Deployment
#
# This file deploys the demo Helm chart to the AKS cluster.

# Generate random MCP API key for authentication
resource "random_password" "mcp_api_key" {
  length  = 32
  special = false
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

  # OpenAI configuration
  openai_endpoint = azurerm_cognitive_account.ai_services.endpoint
  openai_base_url = "${local.openai_endpoint}openai/v1/"
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

# Deploy demo microservices chart
resource "helm_release" "demo" {
  name      = "demo"
  chart     = "${path.module}/../../charts/demo"
  namespace = "default"

  # Use values file from Terraform directory for service configuration
  values = [
    file("${path.module}/helm_values.yaml")
  ]

  # Override registry from Terraform state
  set {
    name  = "registry"
    value = azurerm_container_registry.main.login_server
  }

  # MCP configuration
  set_sensitive {
    name  = "mcpApiKey"
    value = random_password.mcp_api_key.result
  }

  set {
    name  = "mcpCorsOrigins"
    value = "*"
  }

  # OpenAI configuration for visualization generator
  set_sensitive {
    name  = "openai.apiKey"
    value = data.azurerm_cognitive_account.ai_services.primary_access_key
  }

  set {
    name  = "openai.model"
    value = "gpt-5"
  }

  set {
    name  = "openai.baseUrl"
    value = local.openai_base_url
  }

  set {
    name  = "openai.apiVersion"
    value = "preview"
  }

  # Wait for AKS to be ready and ACR permissions to be set
  depends_on = [
    azapi_resource.aks,
    azurerm_role_assignment.aks_acr_pull,
    azurerm_cognitive_account.ai_services
  ]
}

# Output for verification
output "helm_demo_status" {
  description = "Status of the demo Helm release"
  value = {
    name      = helm_release.demo.name
    namespace = helm_release.demo.namespace
    version   = helm_release.demo.version
    status    = helm_release.demo.status
  }
}

output "mcp_api_key" {
  description = "MCP API key for authentication (sensitive)"
  value       = random_password.mcp_api_key.result
  sensitive   = true
}
