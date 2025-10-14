# Deployment artifacts for Azure deployment

## MCP Tools
Folder `mcp_tools` contains Terraform manifest to deploy MCP Servers into Azure Container Apps. For purpose of our course this is provided by teacher so you do not have to deploy your instance (but you can).

## Azure Infrastructure
Folder `infrastructure` container Terraform manifest to deploy infrastructure in Azure to support production deployment of our solution. Components include:
- Azure Kubernetes Service and respective network implementations
- Azure Database for PostgreSQL
- Azure Container Registry
- Azure AI Foundry with gpt-5 model and observability with Application Insights