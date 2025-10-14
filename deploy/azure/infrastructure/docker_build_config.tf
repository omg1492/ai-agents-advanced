# Docker Build Configuration Management
# 
# This file manages the config.yaml file for the docker build script.
# It updates only the registry name while preserving all other configuration.
# Handles cases where file or registry field doesn't exist.

locals {
  docker_build_dir = "${path.module}/../docker_build"
  config_file_path = "${local.docker_build_dir}/config.yaml"
}

# Try to read the existing config file (may not exist)
data "local_file" "build_config" {
  count    = fileexists(local.config_file_path) ? 1 : 0
  filename = local.config_file_path
}

# Determine the content to write
locals {
  # Check if file exists
  file_exists = fileexists(local.config_file_path)

  # Get existing content if file exists, otherwise use template
  existing_content = local.file_exists ? data.local_file.build_config[0].content : ""

  # Check if registry line exists in the content
  has_registry_line = length(regexall("(?m)^registry:", local.existing_content)) > 0

  # Default template for new files
  default_template = <<-EOT
# Azure Container Registry Build Configuration
# 
# This file defines which services to build and push to ACR.
# The registry name is managed by Terraform and should not be edited manually.

# Azure Container Registry name (managed by Terraform)
registry: "${azurerm_container_registry.main.name}"

# Services to build and push
# Add your services here following this structure:
# services:
#   - name: service-name
#     path: ../../../tools/service_directory
#     tag: latest
services: []
EOT

  # Generate the final content based on file state
  final_content = (
    # Case 1: File doesn't exist - use default template
    !local.file_exists ? local.default_template :
    # Case 2: File exists but no registry line - add it after initial comment block
    !local.has_registry_line ? replace(
      local.existing_content,
      "/(^(?:#[^\n]*\n)+)(\n*)/",
      "$1\n# Azure Container Registry name (managed by Terraform)\nregistry: \"${azurerm_container_registry.main.name}\"\n$2"
    ) :
    # Case 3: File exists with registry line - update it
    replace(
      local.existing_content,
      "/registry:\\s*\"?[^\"\\n]+\"?/",
      "registry: \"${azurerm_container_registry.main.name}\""
    )
  )
}

# Write or update the config file
resource "local_file" "build_config" {
  content         = local.final_content
  filename        = local.config_file_path
  file_permission = "0644"

  # Create parent directory if it doesn't exist
  directory_permission = "0755"

  # Only update if ACR has been created
  depends_on = [
    azurerm_container_registry.main
  ]
}

# Output for verification
output "docker_build_config_path" {
  description = "Path to the docker build configuration file"
  value       = local.config_file_path
}

output "acr_name_in_config" {
  description = "ACR name configured in docker build config"
  value       = azurerm_container_registry.main.name
}

output "docker_build_config_status" {
  description = "Status of the docker build configuration"
  value = {
    file_existed = local.file_exists
    had_registry = local.has_registry_line
    action_taken = !local.file_exists ? "created_new_file" : !local.has_registry_line ? "added_registry_line" : "updated_registry_line"
  }
}
