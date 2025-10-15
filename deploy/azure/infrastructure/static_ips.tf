# Static Public IP addresses for external LoadBalancer services
# These IPs are pre-allocated so they're known before deployment,
# enabling deterministic configuration and avoiding chicken-and-egg
# problems with services that need external URLs.

resource "azurerm_public_ip" "mcp_chef_services" {
  name                = "pip-mcp-chef-services-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "mcp-chef-${local.base_name_nodash}"
}

resource "azurerm_public_ip" "mcp_public_farmer_tools" {
  name                = "pip-mcp-public-farmer-tools-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "mcp-farmer-${local.base_name_nodash}"
}

resource "azurerm_public_ip" "mcp_visualization_generator" {
  name                = "pip-mcp-visualization-generator-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "mcp-viz-${local.base_name_nodash}"
}

resource "azurerm_public_ip" "dreamfarm_agent" {
  name                = "pip-dreamfarm-agent-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "dreamfarm-${local.base_name_nodash}"
}

resource "azurerm_public_ip" "keycloak" {
  name                = "pip-keycloak-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "keycloak-${local.base_name_nodash}"
}

resource "azurerm_public_ip" "frontend" {
  name                = "pip-frontend-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "frontend-${local.base_name_nodash}"
}

# Outputs for use in Helm values
output "mcp_chef_services_ip" {
  description = "Static IP address for mcp-chef-services LoadBalancer"
  value       = azurerm_public_ip.mcp_chef_services.ip_address
}

output "mcp_chef_services_fqdn" {
  description = "FQDN for mcp-chef-services LoadBalancer"
  value       = azurerm_public_ip.mcp_chef_services.fqdn
}

output "mcp_public_farmer_tools_ip" {
  description = "Static IP address for mcp-public-farmer-tools LoadBalancer"
  value       = azurerm_public_ip.mcp_public_farmer_tools.ip_address
}

output "mcp_public_farmer_tools_fqdn" {
  description = "FQDN for mcp-public-farmer-tools LoadBalancer"
  value       = azurerm_public_ip.mcp_public_farmer_tools.fqdn
}

output "mcp_visualization_generator_ip" {
  description = "Static IP address for mcp-visualization-generator LoadBalancer"
  value       = azurerm_public_ip.mcp_visualization_generator.ip_address
}

output "mcp_visualization_generator_fqdn" {
  description = "FQDN for mcp-visualization-generator LoadBalancer"
  value       = azurerm_public_ip.mcp_visualization_generator.fqdn
}

output "dreamfarm_agent_ip" {
  description = "Static IP address for dreamfarm-agent LoadBalancer"
  value       = azurerm_public_ip.dreamfarm_agent.ip_address
}

output "dreamfarm_agent_fqdn" {
  description = "FQDN for dreamfarm-agent LoadBalancer"
  value       = azurerm_public_ip.dreamfarm_agent.fqdn
}

output "keycloak_ip" {
  description = "Static IP address for keycloak LoadBalancer"
  value       = azurerm_public_ip.keycloak.ip_address
}

output "keycloak_fqdn" {
  description = "FQDN for keycloak LoadBalancer"
  value       = azurerm_public_ip.keycloak.fqdn
}

output "frontend_ip" {
  description = "Static IP address for frontend LoadBalancer"
  value       = azurerm_public_ip.frontend.ip_address
}

output "frontend_fqdn" {
  description = "FQDN for frontend LoadBalancer"
  value       = azurerm_public_ip.frontend.fqdn
}
