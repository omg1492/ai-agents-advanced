# Azure Container Registry Build Tools

Python script for building and pushing MCP server Docker images to Azure Container Registry using ACR Tasks.

## Prerequisites

- **Azure CLI**: Installed and authenticated (`az login`)
- **Python 3.12+**: With PyYAML package
- **Terraform**: Applied infrastructure in `../infrastructure/` (configures ACR name automatically)
- **config.yaml**: Configuration file in this directory (created manually, ACR name managed by Terraform)

## Quick Start

```powershell
# 1. Install dependencies
uv sync

# 2. Apply Terraform to configure ACR name in config.yaml
cd ../infrastructure
terraform apply
cd ../docker_build

# 3. Authenticate with Azure
az login

# 4. Build and push all services
python build_and_push.py
```

## Configuration

All build configuration is managed through `config.yaml`. The registry name is automatically updated by Terraform, but service definitions are manually managed.

### config.yaml Structure

```yaml
# Azure Container Registry name (managed by Terraform)
registry: "your-registry-name"

# Services to build and push
services:
  - name: service-name          # Image name in ACR
    path: ../../../../path      # Relative path to service directory
    tag: latest                  # Image tag
    description: Description     # Optional description
    port: 8080                   # Optional port number
```

### Adding a New Service

To add a new service to build:

1. Edit `config.yaml` and add a new entry to the `services` array:

```yaml
services:
  - name: my-new-service
    path: ../../../../tools/my_new_service
    tag: latest
    description: My new MCP server
    port: 8014
```

2. Run the build script:

```powershell
python build_and_push.py
```

That's it! No need to modify Python code or Terraform.

## Usage

The script has no command-line arguments. All configuration is in `config.yaml`.

```powershell
# Build all services defined in config.yaml
python build_and_push.py
```

### Changing Image Tags

To build with different tags, edit the `tag` field in `config.yaml` for specific services:

```yaml
services:
  - name: api-stock
    path: ../../../../tools/api_stock
    tag: v1.0.0  # Changed from 'latest'
```

### Temporarily Disabling a Service

To skip building a service, comment it out in `config.yaml`:

```yaml
services:
  - name: api-stock
    path: ../../../../tools/api_stock
    tag: latest
  
  # Temporarily disabled
  # - name: mcp-chef-services
  #   path: ../../../../tools/mcp_chef_services
  #   tag: latest
```

## How It Works

1. **Configuration Loading**: Reads `config.yaml` for registry name and service definitions
2. **Authentication Check**: Verifies Azure CLI is installed and authenticated
3. **Service Validation**: Validates each service configuration and checks paths exist
4. **Build Process**: For each service:
   - Validates Dockerfile exists
   - Runs `az acr build` with proper context and image name
   - ACR Tasks builds the image in Azure and pushes to registry
5. **Summary**: Reports success/failure for each service

## ACR Build Process

The script uses **ACR Quick Tasks** which:
- Build the Docker image in Azure (not locally)
- Automatically push successful builds to the registry
- Stream build logs to your terminal
- Use your Azure CLI authentication (no explicit credentials needed)

Command pattern used:
```bash
az acr build --registry <name> --image <image>:<tag> --file Dockerfile <context>
```

## Terraform Integration

The ACR registry name in `config.yaml` is automatically managed by Terraform:

1. When you run `terraform apply`, it reads the current `config.yaml`
2. It updates only the `registry:` line with the actual ACR name
3. All other lines (comments, services, etc.) are preserved exactly as-is
4. This happens through a regex replacement in `docker_build_config.tf`

**Important**: Never manually edit the `registry:` line in `config.yaml` - it will be overwritten by Terraform.

## Troubleshooting

### "Configuration file not found"
Create a `config.yaml` file in the `docker_build/` directory. See the structure above.

### "Registry name is not configured"
The registry field is set to `PLACEHOLDER_REGISTRY_NAME`. Run `terraform apply` in the infrastructure directory to configure it:
```powershell
cd ../infrastructure
terraform apply
cd ../docker_build
```

### "Azure CLI not authenticated"
Run `az login` and authenticate with your Azure account.

### "Dockerfile not found"
Ensure the `path` in your service configuration points to the correct directory and that a `Dockerfile` exists there.

### Build fails with permissions error
Verify you have appropriate ACR permissions:
```powershell
az acr show --name <acr_name> --query "{Name:name,LoginServer:loginServer}"
```

### "PyYAML is required"
Install the required dependency:
```powershell
uv sync
# or
pip install pyyaml
```

## Examples

### Build All Services
```powershell
python build_and_push.py
```

### Add a New Service
1. Edit `config.yaml`:
```yaml
services:
  # ... existing services ...
  - name: my-analytics-service
    path: ../../../../tools/analytics_service
    tag: latest
    description: Analytics processing service
    port: 8015
```

2. Run the build:
```powershell
python build_and_push.py
```

### Deploy Different Versions
Edit `config.yaml` to set different tags:
```yaml
services:
  - name: api-stock
    path: ../../../../tools/api_stock
    tag: v1.2.0  # Production version
  
  - name: mcp-chef-services
    path: ../../../../tools/mcp_chef_services
    tag: beta    # Beta testing version
```

## Output

The script provides color-coded output:
- **Green ✓**: Success messages
- **Blue ℹ**: Informational messages
- **Yellow ⚠**: Warnings
- **Red ✗**: Errors

Example output:
```
================================================================================
Azure Container Registry - Build and Push
================================================================================

ℹ Configuration loaded from: C:\...\config.yaml
ℹ Registry: rdapps3f1i
ℹ Services to build: 3

ℹ Running: az account show
✓ Azure CLI authenticated as: user@example.com
ℹ Subscription: My Subscription (673af34d-...)

================================================================================
Building api-stock:latest
================================================================================

ℹ Context: C:\git\advanced-ai-applications\tools\api_stock
ℹ Dockerfile: Dockerfile
ℹ Registry: rdapps3f1i
ℹ Image: api-stock:latest
✓ Successfully built and pushed api-stock:latest

...

================================================================================
Build Summary
================================================================================

✓ api-stock: Built and pushed successfully
✓ mcp-chef-services: Built and pushed successfully
✓ mcp-public-farmer-tools: Built and pushed successfully

✓ All 3 service(s) built and pushed successfully!
ℹ Images available in registry: rdapps3f1i.azurecr.io
```

## Integration with AKS

After building images, they're available at:
```
<acr_name>.azurecr.io/api-stock:latest
<acr_name>.azurecr.io/mcp-chef-services:latest
<acr_name>.azurecr.io/mcp-public-farmer-tools:latest
```

Use these image references in Kubernetes manifests or Helm charts for deployment to the AKS cluster.

## Configuration File Format

The `config.yaml` file uses YAML format with the following structure:

```yaml
# Comments are preserved by Terraform
registry: "acr-name"  # This line is managed by Terraform

services:
  - name: string           # Required: Image name in ACR (e.g., "my-service")
    path: string           # Required: Relative path to service directory
    tag: string            # Required: Image tag (e.g., "latest", "v1.0.0")
    description: string    # Optional: Human-readable description
    port: integer          # Optional: Service port number for documentation
```

## Notes

- ACR build happens in Azure, not locally (no Docker daemon required)
- Build logs are streamed in real-time
- Failed builds do not push any images
- PyYAML is the only Python dependency (for YAML parsing)
- All Dockerfiles use `uv` package manager and Python 3.12-slim base
- The script validates paths before attempting to build
- Terraform preserves all config.yaml content except the registry line
