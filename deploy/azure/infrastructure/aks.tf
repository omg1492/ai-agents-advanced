resource "azurerm_user_assigned_identity" "aks" {
  name                = "id-aks-${local.base_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_user_assigned_identity.aks.principal_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.main.id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "aks_network_contributor" {
  principal_id                     = azurerm_user_assigned_identity.aks.principal_id
  role_definition_name             = "Network Contributor"
  scope                            = azurerm_resource_group.main.id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "aks_managed_identity_operator" {
  principal_id                     = azurerm_user_assigned_identity.aks.principal_id
  role_definition_name             = "Managed Identity Operator"
  scope                            = azurerm_user_assigned_identity.aks.id
  skip_service_principal_aad_check = true
}

resource "azapi_resource" "aks" {
  type      = "Microsoft.ContainerService/managedClusters@2025-07-02-preview"
  name      = "aks-${local.base_name}"
  location  = azurerm_resource_group.main.location
  parent_id = azurerm_resource_group.main.id

  identity {
    type = "UserAssigned"
    identity_ids = [
      azurerm_user_assigned_identity.aks.id
    ]
  }

  body = {
    properties = {
      dnsPrefix = "aks-${local.base_name_nodash}"

      kubernetesVersion = "1.31"

      networkProfile = {
        networkPlugin     = "azure"
        networkPluginMode = "overlay"
        networkDataplane  = "cilium"
        networkPolicy     = "cilium"
        loadBalancerSku   = "standard"
        serviceCidr       = "10.0.0.0/16"
        dnsServiceIP      = "10.0.0.10"
      }

      nodeProvisioningProfile = {
        mode = "Auto"
      }

      agentPoolProfiles = [
        {
          name         = "system"
          mode         = "System"
          count        = 1
          vmSize       = "Standard_D2ads_v6"
          osDiskSizeGB = 110
          osDiskType   = "Ephemeral"
          osType       = "Linux"
          osSKU        = "AzureLinux"
          type         = "VirtualMachineScaleSets"
          vnetSubnetID = azurerm_subnet.aks.id
        }
      ]

      identityProfile = {
        kubeletidentity = {
          resourceId = azurerm_user_assigned_identity.aks.id
          clientId   = azurerm_user_assigned_identity.aks.client_id
          objectId   = azurerm_user_assigned_identity.aks.principal_id
        }
      }

      oidcIssuerProfile = {
        enabled = true
      }

      securityProfile = {
        workloadIdentity = {
          enabled = true
        }
      }

      enableRBAC = true
    }

    sku = {
      name = "Base"
      tier = "Standard"
    }
  }

  depends_on = [
    azurerm_role_assignment.aks_acr_pull,
    azurerm_role_assignment.aks_network_contributor,
    azurerm_role_assignment.aks_managed_identity_operator,
    azurerm_subnet_network_security_group_association.aks
  ]
}
