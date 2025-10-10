variable "location" {
  description = "Azure region where all resources will be deployed."
  type        = string
  default     = "swedencentral"
}

variable "resource_group_name" {
  description = "Name of the Azure Resource Group that will contain all MCP server resources."
  type        = string
  default     = "rg-advanced-ai-apps"
}

variable "farmer_tools_image" {
  description = <<DESC
Docker image for the farmer tools MCP server.
Example: ghcr.io/tkubica12/advanced-ai-applications/mcp-public-farmer-tools:latest
DESC
  type        = string
  default     = "ghcr.io/tkubica12/advanced-ai-applications/mcp-public-farmer-tools:latest"
}

variable "farmer_tools_min_replicas" {
  description = "Minimum number of replicas for farmer tools (0 = scale-to-zero)"
  type        = number
  default     = 0
}

variable "farmer_tools_api_key" {
  description = "Static bearer token for authenticating requests to the farmer tools MCP server."
  type        = string
  sensitive   = true
}

variable "viz_gen_image" {
  description = <<DESC
Docker image for the visualization generator MCP server.
Example: ghcr.io/tkubica12/advanced-ai-applications/mcp-visualization-generator:latest
DESC
  type        = string
  default     = "ghcr.io/tkubica12/advanced-ai-applications/mcp-visualization-generator:latest"
}

variable "viz_gen_min_replicas" {
  description = "Minimum number of replicas for visualization generator (0 = scale-to-zero)"
  type        = number
  default     = 0
}

variable "viz_gen_api_key" {
  description = "Static bearer token for authenticating requests to the visualization generator MCP server."
  type        = string
  sensitive   = true
}

variable "viz_gen_openai_api_key" {
  description = "OpenAI API key for the visualization generator (Azure OpenAI or OpenAI)."
  type        = string
  sensitive   = true
}

variable "viz_gen_openai_base_url" {
  description = <<DESC
OpenAI base URL for Azure OpenAI endpoint.
Example: https://your-resource.openai.azure.com/openai/v1/
Leave empty for standard OpenAI.
DESC
  type        = string
  default     = ""
}

variable "viz_gen_openai_api_version" {
  description = "API version for Azure OpenAI (e.g., 'preview', '2024-02-15-preview')."
  type        = string
  default     = "preview"
}

variable "viz_gen_openai_model" {
  description = <<DESC
OpenAI model to use for visualization generation.
DESC
  type        = string
  default     = "gpt-5"
}

variable "chef_services_image" {
  description = <<DESC
Docker image for the chef services MCP server.
Example: ghcr.io/tkubica12/advanced-ai-applications/mcp-chef-services:latest
DESC
  type        = string
  default     = "ghcr.io/tkubica12/advanced-ai-applications/mcp-chef-services:latest"
}

variable "chef_services_min_replicas" {
  description = "Minimum number of replicas for chef services (0 = scale-to-zero)"
  type        = number
  default     = 0
}

variable "chef_services_api_key" {
  description = "Static bearer token for authenticating requests to the chef services MCP server."
  type        = string
  sensitive   = true
}
