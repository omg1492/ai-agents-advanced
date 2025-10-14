resource "random_string" "suffix" {
  length  = 4
  special = false
  upper   = false
  numeric = true
}

locals {
  base_name        = "${var.prefix}-${random_string.suffix.result}"
  base_name_nodash = "${var.prefix}${random_string.suffix.result}"
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.base_name}"
  location = var.location
}
