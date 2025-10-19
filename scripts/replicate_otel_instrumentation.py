"""
Script to replicate OpenTelemetry logging and metrics instrumentation across all Python services.

This script copies the otel_logging.py and otel_metrics.py modules to other services
and provides guidance on integration.

Services to update:
1. agents/chef-agent ✓
2. tools/api_stock ✓
3. tools/mcp_chef_services ✓
4. tools/mcp_public_farmer_tools ✓
5. tools/mcp_visualization_generator ✓

Each service needs:
1. Copy src/utils/otel_logging.py and otel_metrics.py
2. Update pyproject.toml dependencies
3. Update main.py to initialize logging/metrics
4. Update .env.template with new env vars
"""

import shutil
import os
from pathlib import Path

# Source files from dreamfarm-agent
SOURCE_LOGGING = Path("agents/dreamfarm-agent/src/utils/otel_logging.py")
SOURCE_METRICS = Path("agents/dreamfarm-agent/src/utils/otel_metrics.py")

# Target services
SERVICES = [
    {
        "name": "chef-agent",
        "path": "agents/chef-agent",
        "utils_dir": "agents/chef-agent/src/utils"
    },
    {
        "name": "api-stock",
        "path": "tools/api_stock",
        "utils_dir": "tools/api_stock/src/utils"
    },
    {
        "name": "mcp-chef-services",
        "path": "tools/mcp_chef_services",
        "utils_dir": "tools/mcp_chef_services/src/utils"
    },
    {
        "name": "mcp-public-farmer-tools",
        "path": "tools/mcp_public_farmer_tools",
        "utils_dir": "tools/mcp_public_farmer_tools/src/utils"
    },
    {
        "name": "mcp-visualization-generator",
        "path": "tools/mcp_visualization_generator",
        "utils_dir": "tools/mcp_visualization_generator/src/utils"
    }
]

# Dependencies to add to pyproject.toml
DEPENDENCIES_TO_ADD = '''    # Logging and metrics support (OpenTelemetry)
    "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",  # OTLP gRPC exporter for logs/metrics
    "opentelemetry-distro>=0.41b0",  # Auto-instrumentation distribution
    "opentelemetry-instrumentation>=0.41b0",  # Instrumentation utilities'''

# Environment variables to add to .env.template
ENV_VARS_TO_ADD = '''
# OpenTelemetry Configuration (traces, logs, and metrics)
# Set OTEL_EXPORTER_OTLP_ENDPOINT to enable observability (leave empty to disable)
# The collector will route traces to Tempo, logs to Loki, and metrics to Prometheus
OTEL_SERVICE_NAME={service_name}
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPERIMENT=production
OTEL_INSTRUMENTATION_PROVIDER=openinference
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true'''

def main():
    print("OpenTelemetry Logging/Metrics Replication Script")
    print("=" * 60)
    
    for service in SERVICES:
        print(f"\nProcessing: {service['name']}")
        print("-" * 60)
        
        # Create utils directory if it doesn't exist
        utils_dir = Path(service['utils_dir'])
        utils_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy logging module
        target_logging = utils_dir / "otel_logging.py"
        if SOURCE_LOGGING.exists():
            shutil.copy2(SOURCE_LOGGING, target_logging)
            print(f"✓ Copied otel_logging.py to {target_logging}")
        else:
            print(f"✗ Source not found: {SOURCE_LOGGING}")
        
        # Copy metrics module
        target_metrics = utils_dir / "otel_metrics.py"
        if SOURCE_METRICS.exists():
            shutil.copy2(SOURCE_METRICS, target_metrics)
            print(f"✓ Copied otel_metrics.py to {target_metrics}")
        else:
            print(f"✗ Source not found: {SOURCE_METRICS}")
        
        # Create __init__.py if it doesn't exist
        init_file = utils_dir / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            print(f"✓ Created {init_file}")
        
        print(f"\nNext steps for {service['name']}:")
        print(f"1. Update {service['path']}/pyproject.toml with:")
        print(DEPENDENCIES_TO_ADD)
        print(f"\n2. Update {service['path']}/src/main.py to initialize logging/metrics")
        print(f"3. Update {service['path']}/.env.template with:")
        print(ENV_VARS_TO_ADD.format(service_name=service['name']))

if __name__ == "__main__":
    main()
