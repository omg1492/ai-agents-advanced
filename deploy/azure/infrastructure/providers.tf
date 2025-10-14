terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2"
    }
  }
}

provider "azurerm" {
  subscription_id = "673af34d-6b28-41dc-bc7b-f507418045e6"
  features {}
}

provider "azapi" {
  subscription_id = "673af34d-6b28-41dc-bc7b-f507418045e6"
}
