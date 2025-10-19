variable "location" {
  description = <<-EOT
    The Azure region where resources will be deployed.
    This location should support all required services including AKS, Container Registry,
    and AI/ML capabilities. Sweden Central is recommended for European deployments
    due to its comprehensive service availability and sustainability focus.
  EOT
  type        = string
  default     = "swedencentral"
}

variable "prefix" {
  description = <<-EOT
    Prefix used for naming all resources in this deployment.
    Combined with random characters to ensure global uniqueness where required.
    Should be short (3-6 characters) and use only lowercase letters to comply
    with naming restrictions across different Azure resource types.
    Example: "rdapps" will generate names like "rdapps-a1b2" or "rdappsa1b2".
  EOT
  type        = string
  default     = "rdapps"

  validation {
    condition     = can(regex("^[a-z0-9]{3,10}$", var.prefix))
    error_message = "Prefix must be 3-10 characters, containing only lowercase letters and numbers."
  }
}

variable "tavily_api_key" {
  description = <<-EOT
    API key for Tavily search service.
    Used by the dreamfarm-agent for agentic search capabilities.
    This is a sensitive value and should be provided via environment variable
    or secure parameter file. Do not commit this to version control.
    Obtain your API key from: https://tavily.com
  EOT
  type      = string
  sensitive = true
}

variable "domain" {
  description = <<-EOT
    Domain name for the application.
    All services will be exposed as subdomains under this domain.
    Frontend will be at the apex (e.g., dreamfarm.tomasdemo.org)
    Services will be at servicename.domain (e.g., keycloak.dreamfarm.tomasdemo.org)
    
    DNS Setup Required:
    1. Create CNAME for domain pointing to the ingress FQDN
    2. Create CNAME for *.domain pointing to the ingress FQDN
    
    Example with Azure DNS:
    - dreamfarm.tomasdemo.org -> ingress-rdappsa2tj.swedencentral.cloudapp.azure.com
    - *.dreamfarm.tomasdemo.org -> ingress-rdappsa2tj.swedencentral.cloudapp.azure.com
  EOT
  type        = string
  default     = "dreamfarm.tomasdemo.org"
}

variable "environment" {
  description = <<-EOT
    Environment identifier for tagging and naming.
    Used to differentiate between dev, staging, and production deployments.
  EOT
  type        = string
  default     = "production"
}

variable "otel_experiment" {
  description = <<-EOT
    OpenTelemetry experiment identifier for A/B testing and trace filtering.
    This value is added as a span attribute to all traces, enabling:
    - Filtering traces by experiment in Grafana Tempo
    - A/B testing different configurations or models
    - Tracking canary deployments
    - Separating production vs. experimental traffic
    
    Common values:
    - "default" - Standard production traffic
    - "production" - Explicit production environment
    - "canary" - Canary deployment testing
    - "experiment-v2" - Specific experiment identifier
    
    Set via environment variable or Terraform variable:
    export TF_VAR_otel_experiment="canary"
  EOT
  type        = string
  default     = "default"
}
