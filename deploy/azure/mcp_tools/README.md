# Terraform: Deploy MCP Servers to Azure Container Apps

This Terraform configuration deploys two MCP (Model Context Protocol) servers to Azure Container Apps:

1. **Farmer Tools MCP Server** - Public farmer tools API
2. **Visualization Generator MCP Server** - HTML/CSS/JS visualization generation using OpenAI

## Architecture

- **Azure Container Apps Environment** - Managed Kubernetes infrastructure with auto-scaling
- **Log Analytics Workspace** - Centralized logging and monitoring
- **Container Apps** - Serverless containers with HTTP ingress
- **Secrets Management** - Secure handling of API keys via Container Apps secrets

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli) authenticated (`az login`)
- Docker images pushed to container registry (GHCR, ACR, etc.)
- Azure subscription with permissions to create resources

## Quick Start

### 1. Configure Secrets

Copy the sample secrets file and fill in real values:

```powershell
Copy-Item secrets.auto.tfvars-sample secrets.auto.tfvars
```

Edit `secrets.auto.tfvars` with your actual secrets:
- `farmer_tools_api_key` - Strong random token for farmer tools auth
- `viz_gen_api_key` - Strong random token for viz generator auth
- `viz_gen_openai_api_key` - Your Azure OpenAI or OpenAI API key
- Container registry credentials (if using private registry)

### 2. Update Configuration

Edit `configs.auto.tfvars` to customize:
- Azure region and resource names
- Container image references
- Resource sizing (CPU, memory, replicas)
- CORS origins
- OpenAI model and settings

### 3. Deploy

```powershell
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy infrastructure
terraform apply
```

### 4. Verify Deployment

```powershell
# Get outputs
terraform output

# Test health endpoints
$farmerUrl = terraform output -raw farmer_tools_url
$vizUrl = terraform output -raw viz_gen_url

Invoke-RestMethod "${farmerUrl}/health"
Invoke-RestMethod "${vizUrl}/health"
```

## Configuration

### Required Secrets (secrets.auto.tfvars)

| Variable | Description | Example |
|----------|-------------|---------|
| `farmer_tools_api_key` | Bearer token for farmer tools auth | `advancedaiapps2025` |
| `viz_gen_api_key` | Bearer token for viz generator auth | `Azure12345678` |
| `viz_gen_openai_api_key` | OpenAI/Azure OpenAI API key | `sk-...` or Azure key |

### Optional Secrets

| Variable | Description | When Needed |
|----------|-------------|-------------|
| `container_registry_username` | Registry username | Private registries |
| `container_registry_password` | Registry password | Private registries |

### Non-Sensitive Config (configs.auto.tfvars)

| Variable | Default | Description |
|----------|---------|-------------|
| `location` | `eastus` | Azure region |
| `resource_group_name` | `rg-mcp-tools` | Resource group name |
| `farmer_tools_image` | - | Docker image reference |
| `viz_gen_image` | - | Docker image reference |
| `viz_gen_openai_base_url` | `""` | Azure OpenAI endpoint URL |
| `viz_gen_openai_model` | `gpt-4o` | Model name |

## Container Sizing

### Farmer Tools (Lightweight)
- CPU: 0.5 cores
- Memory: 1Gi
- Replicas: 1-3 (auto-scale)

### Visualization Generator (LLM-intensive)
- CPU: 0.75 cores
- Memory: 1.5Gi
- Replicas: 1-3 (auto-scale)

Adjust in `configs.auto.tfvars` based on your workload.

## Authentication

Both servers use static bearer token authentication:

```bash
# Farmer Tools
curl -H "Authorization: Bearer <farmer_tools_api_key>" \
  https://<fqdn>/mcp

# Visualization Generator
curl -H "Authorization: Bearer <viz_gen_api_key>" \
  https://<fqdn>/mcp
```

## Monitoring

Access logs via Azure Portal:
1. Navigate to Container App
2. Select **Log stream** or **Logs**
3. Query with Kusto (KQL)

Example query:
```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "ca-mcp-farmer-tools"
| project TimeGenerated, Log_s
| order by TimeGenerated desc
```

## Cleanup

```powershell
terraform destroy
```

## File Structure

```
mcp_tools/
├── main.tf                              # Resource group, Log Analytics
├── providers.tf                         # Provider configuration
├── variables.tf                         # Variable definitions
├── outputs.tf                           # Output values
├── container_app.env.tf                 # Container Apps Environment
├── container_app.farmer-tools.tf        # Farmer Tools Container App
├── container_app.visualization-generator.tf  # Viz Gen Container App
├── configs.auto.tfvars                  # Non-sensitive config
├── secrets.auto.tfvars                  # Sensitive values (git-ignored)
├── secrets.auto.tfvars-sample           # Template for secrets
├── .gitignore                           # Terraform git ignore
└── README.md                            # This file
```

## Troubleshooting

### Container fails to start
- Check image exists and registry credentials are correct
- Review container logs in Azure Portal
- Verify environment variables are set correctly

### Authentication fails
- Ensure API keys in `secrets.auto.tfvars` match client configuration
- Check `Authorization: Bearer <token>` header format

### OpenAI errors (Viz Generator)
- Verify `viz_gen_openai_api_key` is valid
- Confirm `viz_gen_openai_base_url` format (must end with `/openai/v1/` for Azure)
- Check model name matches your deployment

## Security Best Practices

1. **Never commit** `secrets.auto.tfvars` to version control
2. Use **Azure Key Vault** for production secrets (not static tfvars)
3. Rotate API keys regularly
4. Restrict CORS origins in production (don't use `*`)
5. Enable Container Apps authentication/authorization for additional security layer

## Cost Optimization

- Set `min_replicas = 0` for scale-to-zero (dev environments)
- Use Azure Container Apps Free Grant (180,000 vCPU-seconds/month)
- Monitor usage via Azure Cost Management

## Next Steps

- Configure custom domains and SSL certificates
- Integrate with Azure API Management
- Set up Azure Monitor alerts
- Implement CI/CD pipeline for automated deployments
- Add virtual network integration for private endpoints