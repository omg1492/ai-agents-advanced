resource "azurerm_container_registry" "main" {
  name                = local.base_name_nodash
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
}
