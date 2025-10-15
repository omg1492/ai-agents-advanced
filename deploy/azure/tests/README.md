# Smoke Tests for Deployed Infrastructure

Post-deployment smoke tests to verify connectivity and basic health of all deployed services.

## Setup

### Automatic Setup (Recommended)

After deploying the infrastructure, generate the `.env` file automatically:

```powershell
# Generate .env with service IPs (waits for LoadBalancer IPs)
uv run generate_env.py

# Or without waiting (if LoadBalancers are already assigned)
uv run generate_env.py --no-wait
```

This script:
- Fetches LoadBalancer IPs from Kubernetes services
- Retrieves MCP API key from Kubernetes secrets
- Generates `.env` file with all required configuration
- Waits for LoadBalancer IP assignment (up to 5 minutes)

### Manual Setup (Alternative)

If you prefer to configure manually:

1. **Get Service IPs:**
```powershell
# Get all service IPs
kubectl get svc -o wide

# Get specific service IPs
kubectl get svc mcp-chef-services -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
kubectl get svc mcp-public-farmer-tools -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
kubectl get svc mcp-visualization-generator -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
kubectl get svc api-stock -o jsonpath='{.spec.clusterIP}'
```

2. **Get MCP API Key:**
```powershell
cd ..\infrastructure
terraform output -raw mcp_api_key
```

3. **Edit `.env` file:**
```properties
MCP_API_KEY=<from-terraform>
MCP_CHEF_SERVICES_URL=http://<ip>:8001
MCP_PUBLIC_FARMER_TOOLS_URL=http://<ip>:8002
MCP_VISUALIZATION_GENERATOR_URL=http://<ip>:8003
API_STOCK_URL=http://<cluster-ip>:8000
```

## Running Tests

Execute the smoke tests:

```powershell
# Test external services only (default)
uv run python main.py

# Test both external and internal services
uv run python main.py --include-internal
```

### Command Options

- `--include-internal`: Include internal (ClusterIP) services in tests. By default, only external LoadBalancer services are tested since internal services are not accessible from outside the cluster.

## What's Tested

### Connectivity Tests
- **MCP Visualization Generator** - `/health` endpoint via LoadBalancer IP
- **MCP Public Farmer Tools** - `/health` endpoint via LoadBalancer IP
- **MCP Chef Services** - `/health` endpoint via LoadBalancer IP
- **API Stock Service** - `/health` endpoint via ClusterIP (internal)

## Output

The tests provide color-coded output:
- ✓ Green: Test passed (HTTP 200)
- ✗ Red: Test failed (connection error, timeout, non-200 status)

A summary is displayed at the end showing total passed/failed counts.

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed or configuration error