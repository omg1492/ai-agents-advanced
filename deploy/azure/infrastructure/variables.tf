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
