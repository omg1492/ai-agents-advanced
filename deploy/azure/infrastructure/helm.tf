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

  # OpenAI configuration
  openai_endpoint = azurerm_cognitive_account.ai_services.endpoint
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

# Deploy demo microservices chart
resource "helm_release" "demo" {
  name      = "demo"
  chart     = "${path.module}/../../charts/demo"
  namespace = "default"

  # Override registry from Terraform state
  set {
    name  = "registry"
    value = azurerm_container_registry.main.login_server
  }

  # MCP API key
  set_sensitive {
    name  = "mcpApiKey"
    value = random_password.mcp_api_key.result
  }

  # OpenAI configuration
  set_sensitive {
    name  = "openai.apiKey"
    value = data.azurerm_cognitive_account.ai_services.primary_access_key
  }

  set {
    name  = "openai.baseUrl"
    value = local.openai_base_url
  }

  # PostgreSQL configuration (Azure Database for PostgreSQL Flexible Server)
  set {
    name  = "postgres.host"
    value = azurerm_postgresql_flexible_server.main.fqdn
  }

  set {
    name  = "postgres.port"
    value = "5432"
  }

  set {
    name  = "postgres.database"
    value = azurerm_postgresql_flexible_server_database.main.name
  }

  set {
    name  = "postgres.username"
    value = azurerm_postgresql_flexible_server.main.administrator_login
  }

  set_sensitive {
    name  = "postgres.password"
    value = azurerm_postgresql_flexible_server.main.administrator_password
  }

  set {
    name  = "postgres.jdbcUrl"
    value = "jdbc:postgresql://${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}"
  }

  # Keycloak configuration
  set_sensitive {
    name  = "keycloak.adminPassword"
    value = random_password.keycloak_admin.result
  }

  set {
    name  = "keycloak.hostname"
    value = azurerm_public_ip.keycloak.fqdn
  }

  # Tavily API key (you'll need to provide this)
  set_sensitive {
    name  = "tavily.apiKey"
    value = var.tavily_api_key
  }

  # Chef agent MCP URL (uses static IP)
  set {
    name  = "chefAgent.mcpUrl"
    value = "http://${azurerm_public_ip.mcp_chef_services.ip_address}/mcp"
  }

  # Dreamfarm agent URLs
  set {
    name  = "dreamfarmAgent.farmerToolsUrl"
    value = "http://${azurerm_public_ip.mcp_public_farmer_tools.ip_address}/mcp"
  }

  set {
    name  = "dreamfarmAgent.visualizationUrl"
    value = "http://${azurerm_public_ip.mcp_visualization_generator.ip_address}/mcp"
  }

  set {
    name  = "dreamfarmAgent.keycloakUrl"
    value = "http://${azurerm_public_ip.keycloak.ip_address}"
  }

  # Frontend configuration
  set {
    name  = "frontend.backendUrl"
    value = "http://${azurerm_public_ip.dreamfarm_agent.ip_address}"
  }

  set {
    name  = "frontend.keycloakUrl"
    value = "http://${azurerm_public_ip.keycloak.ip_address}"
  }

  set {
    name  = "frontend.redirectUri"
    value = "http://${azurerm_public_ip.frontend.ip_address}/"
  }

  # Static IP configuration
  set {
    name  = "staticIPResourceGroup"
    value = azurerm_resource_group.main.name
  }

  set {
    name  = "staticIPNames.mcpChefServices"
    value = azurerm_public_ip.mcp_chef_services.name
  }

  set {
    name  = "staticIPNames.mcpPublicFarmerTools"
    value = azurerm_public_ip.mcp_public_farmer_tools.name
  }

  set {
    name  = "staticIPNames.mcpVisualizationGenerator"
    value = azurerm_public_ip.mcp_visualization_generator.name
  }

  set {
    name  = "staticIPNames.dreamfarmAgent"
    value = azurerm_public_ip.dreamfarm_agent.name
  }

  set {
    name  = "staticIPNames.keycloak"
    value = azurerm_public_ip.keycloak.name
  }

  set {
    name  = "staticIPNames.frontend"
    value = azurerm_public_ip.frontend.name
  }

  # Wait for AKS to be ready, ACR permissions, and static IPs to be created
  depends_on = [
    azapi_resource.aks,
    azurerm_role_assignment.aks_acr_pull,
    azurerm_cognitive_account.ai_services,
    azurerm_postgresql_flexible_server.main,
    azurerm_public_ip.mcp_chef_services,
    azurerm_public_ip.mcp_public_farmer_tools,
    azurerm_public_ip.mcp_visualization_generator,
    azurerm_public_ip.dreamfarm_agent,
    azurerm_public_ip.keycloak,
    azurerm_public_ip.frontend
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

# Generate .env file for tests with service IPs and credentials
resource "local_file" "test_env" {
  filename = "${path.module}/../tests/.env"
  content  = <<-EOT
    # Service IPs for deployed services
    # Automatically generated by Terraform
    # DO NOT EDIT MANUALLY - Changes will be overwritten

    # MCP API Key for authentication
    MCP_API_KEY=${random_password.mcp_api_key.result}

    # OpenAI Configuration
    OPENAI_API_KEY=${data.azurerm_cognitive_account.ai_services.primary_access_key}
    OPENAI_BASE_URL=${local.openai_base_url}

    # PostgreSQL Configuration (Azure Database for PostgreSQL)
    POSTGRES_HOST=${azurerm_postgresql_flexible_server.main.fqdn}
    POSTGRES_PORT=5432
    POSTGRES_DATABASE=${azurerm_postgresql_flexible_server_database.main.name}
    POSTGRES_USER=${azurerm_postgresql_flexible_server.main.administrator_login}
    POSTGRES_PASSWORD=${azurerm_postgresql_flexible_server.main.administrator_password}

    # Keycloak Configuration
    KEYCLOAK_ADMIN_PASSWORD=${random_password.keycloak_admin.result}
    KEYCLOAK_URL=http://${azurerm_public_ip.keycloak.ip_address}

    # Tavily API Key
    TAVILY_API_KEY=${var.tavily_api_key}

    # Service IPs (LoadBalancer external IPs)
    MCP_CHEF_SERVICES_IP=${azurerm_public_ip.mcp_chef_services.ip_address}
    MCP_PUBLIC_FARMER_IP=${azurerm_public_ip.mcp_public_farmer_tools.ip_address}
    MCP_VISUALIZATION_IP=${azurerm_public_ip.mcp_visualization_generator.ip_address}
    DREAMFARM_AGENT_IP=${azurerm_public_ip.dreamfarm_agent.ip_address}
    KEYCLOAK_IP=${azurerm_public_ip.keycloak.ip_address}
    FRONTEND_IP=${azurerm_public_ip.frontend.ip_address}

    # Frontend URL
    FRONTEND_URL=http://${azurerm_public_ip.frontend.ip_address}

    # API Services (ClusterIP - for internal access only)
    # Note: API Stock and Chef Agent are internal only, use kubectl port-forward to access
    # API_STOCK_URL=http://api-stock
    # CHEF_AGENT_URL=http://chef-agent
  EOT

  # Only create after deployment is complete
  depends_on = [
    helm_release.demo
  ]
}

output "test_env_file" {
  description = "Path to generated .env file for tests"
  value       = local_file.test_env.filename
}
