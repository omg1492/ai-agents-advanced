# NGINX Ingress Controller and cert-manager installation
#
# This file manages:
# - Public IP for ingress controller
# - NGINX Ingress Controller installation via Helm
# - cert-manager installation for TLS certificate management

# Create public IP for NGINX Ingress Controller
resource "azurerm_public_ip" "ingress" {
  name                = "pip-ingress-${local.base_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "ingress-${local.base_name_nodash}"

  tags = {
    environment = var.environment
    project     = "dreamfarm"
  }
}

# Install NGINX Ingress Controller
resource "helm_release" "nginx_ingress" {
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  namespace        = "ingress-nginx"
  create_namespace = true
  version          = "4.13.3"

  values = [
    yamlencode({
      controller = {
        service = {
          annotations = {
            "service.beta.kubernetes.io/azure-load-balancer-resource-group"            = azurerm_resource_group.main.name
            "service.beta.kubernetes.io/azure-pip-name"                                = azurerm_public_ip.ingress.name
            "service.beta.kubernetes.io/azure-load-balancer-health-probe-request-path" = "/healthz"
          }
          loadBalancerIP = azurerm_public_ip.ingress.ip_address
        }
        # Enable support for SSE and streaming (critical for MCP servers)
        config = {
          "proxy-read-timeout"      = "3600"
          "proxy-send-timeout"      = "3600"
          "proxy-connect-timeout"   = "3600"
          "proxy-buffering"         = "off"
          "proxy-request-buffering" = "off"
        }
      }
    })
  ]

  depends_on = [
    azapi_resource.aks,
    azurerm_public_ip.ingress
  ]
}

# Install cert-manager for automatic TLS certificate management
resource "helm_release" "cert_manager" {
  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  version          = "v1.18.3"

  set {
    name  = "crds.enabled"
    value = "true"
  }

  depends_on = [
    azapi_resource.aks
  ]
}

# Wait for cert-manager to be ready before creating ClusterIssuer
resource "time_sleep" "wait_for_cert_manager" {
  create_duration = "30s"

  depends_on = [
    helm_release.cert_manager
  ]
}

# Outputs
output "ingress_ip" {
  description = "Public IP address for NGINX Ingress Controller"
  value       = azurerm_public_ip.ingress.ip_address
}

output "ingress_fqdn" {
  description = "FQDN for NGINX Ingress Controller"
  value       = azurerm_public_ip.ingress.fqdn
}
