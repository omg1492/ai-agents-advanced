resource "azurerm_cognitive_account" "ai_services" {
  name                = "ai-${local.base_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  kind                = "AIServices"
  sku_name            = "S0"
}

resource "azurerm_cognitive_deployment" "gpt5" {
  name                 = "gpt-5"
  cognitive_account_id = azurerm_cognitive_account.ai_services.id

  model {
    format  = "OpenAI"
    name    = "gpt-5"
    version = "2025-08-07"
  }

  sku {
    name     = "GlobalStandard"
    capacity = 100
  }
}
