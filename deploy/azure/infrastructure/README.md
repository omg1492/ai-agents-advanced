# Azure Infrastructure Deployment

This directory contains Terraform configuration for deploying the complete Azure infrastructure for the Dreamfarm AI application.

## Architecture

- **AKS Cluster**: Managed Kubernetes with autoscaling
- **Container Registry**: Azure Container Registry for Docker images
- **AI Services**: Azure OpenAI for LLM capabilities
- **Database**: Azure PostgreSQL Flexible Server
- **Ingress**: NGINX Ingress Controller with Let's Encrypt TLS certificates
- **Networking**: Single public IP with hostname-based routing

## Prerequisites

- Azure CLI installed and authenticated
- Terraform >= 1.5.0
- Tavily API key for search capabilities

## Quick Start

1. **Initialize Terraform**:
   ```powershell
   terraform init
   ```

2. **Set Required Variables**:
   ```powershell
   $env:TF_VAR_tavily_api_key = "your-tavily-api-key"
   ```

3. **Review Plan**:
   ```powershell
   terraform plan
   ```

4. **Deploy Infrastructure**:
   ```powershell
   terraform apply
   ```

5. **Get Ingress FQDN for DNS**:
   ```powershell
   terraform output ingress_fqdn
   ```

## DNS Configuration

After deployment, configure these DNS records:

```
CNAME: dreamfarm.tomasdemo.org → <ingress_fqdn>
CNAME: *.dreamfarm.tomasdemo.org → <ingress_fqdn>
```

Example with Azure DNS:
```powershell
$ingressFqdn = terraform output -raw ingress_fqdn
az network dns record-set cname set-record -g dns-rg -z tomasdemo.org -n dreamfarm -c $ingressFqdn
az network dns record-set cname set-record -g dns-rg -z tomasdemo.org -n "*.dreamfarm" -c $ingressFqdn
```

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `location` | Azure region | `swedencentral` |
| `prefix` | Resource name prefix | `rdapps` |
| `domain` | Application domain | `dreamfarm.tomasdemo.org` |
| `environment` | Environment tag | `production` |
| `tavily_api_key` | Tavily API key (required) | - |

## Service URLs

After DNS configuration and certificate issuance (5-10 minutes):

- **Frontend**: https://dreamfarm.tomasdemo.org
- **Keycloak**: https://keycloak.dreamfarm.tomasdemo.org
- **Dreamfarm Agent**: https://dreamfarm-agent.dreamfarm.tomasdemo.org
- **MCP Services**: https://mcp-*.dreamfarm.tomasdemo.org

## HTTPS & Certificates

- **cert-manager**: Automatically manages Let's Encrypt certificates
- **ClusterIssuer**: `letsencrypt-prod` (HTTP-01 challenge)
- **Auto-renewal**: Certificates renewed before expiration

Check certificate status:
```powershell
kubectl get certificates
kubectl describe certificate <cert-name>
```

## Streaming Support (MCP)

NGINX Ingress is configured for Server-Sent Events (SSE):
- `proxy-buffering: off`
- `proxy-read-timeout: 3600s`
- `proxy-request-buffering: off`

## Outputs

- `ingress_ip`: Public IP address for ingress
- `ingress_fqdn`: Azure-provided FQDN for ingress
- `mcp_api_key`: Generated API key for MCP authentication
- `helm_demo_status`: Helm release information
- `test_env_file`: Path to generated .env for tests

## Troubleshooting

**Certificates not issuing?**
```powershell
kubectl get challenges
kubectl describe certificate <cert-name>
kubectl logs -n cert-manager deployment/cert-manager
```

**DNS not resolving?**
```powershell
nslookup dreamfarm.tomasdemo.org
nslookup keycloak.dreamfarm.tomasdemo.org
```

**Check ingress controller:**
```powershell
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

## Clean Up

```powershell
terraform destroy
```

**Note**: You may need to manually delete the AKS node resource group if it persists.

## Files

- `main.tf` - Resource group and locals
- `aks.tf` - AKS cluster configuration
- `acr.tf` - Container Registry
- `ai_services.tf` - Azure OpenAI
- `postgres.tf` - PostgreSQL database
- `ingress.tf` - NGINX Ingress & cert-manager
- `helm.tf` - Demo application deployment
- `variables.tf` - Input variables
- `providers.tf` - Terraform providers
