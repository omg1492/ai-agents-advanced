#!/usr/bin/env python3
"""
Generate .env file for tests by fetching LoadBalancer IPs from Kubernetes.

This script queries the Kubernetes cluster to get the actual service IPs
and populates the .env file with the correct values.
"""

import subprocess
import sys
from pathlib import Path


def run_kubectl(args: list[str]) -> str:
    """Run kubectl command and return output."""
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running kubectl: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print("Error: kubectl not found. Please install kubectl.", file=sys.stderr)
        sys.exit(1)


def get_service_ip(service_name: str, ip_type: str = "loadbalancer") -> str:
    """
    Get service IP from Kubernetes.
    
    Args:
        service_name: Name of the service
        ip_type: Type of IP to retrieve - "loadbalancer" or "clusterip"
    
    Returns:
        Service IP address or "N/A" if not available
    """
    try:
        if ip_type == "loadbalancer":
            # Get LoadBalancer ingress IP
            ip = run_kubectl([
                "get", "svc", service_name,
                "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"
            ])
        else:
            # Get ClusterIP
            ip = run_kubectl([
                "get", "svc", service_name,
                "-o", "jsonpath={.spec.clusterIP}"
            ])
        
        return ip if ip else "N/A"
    except Exception as e:
        print(f"Warning: Could not get IP for {service_name}: {e}", file=sys.stderr)
        return "N/A"


def get_mcp_api_key() -> str:
    """Get MCP API key from Kubernetes secret or Terraform output."""
    # Try Kubernetes secret first
    try:
        key = run_kubectl([
            "get", "secret", "mcp-secrets",
            "-o", "jsonpath={.data.MCP_API_KEY}"
        ])
        if key:
            # Decode base64
            result = subprocess.run(
                ["powershell", "-Command", f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{key}'))"],
                capture_output=True,
                text=True,
                check=True,
            )
            decoded_key = result.stdout.strip()
            if decoded_key:
                return decoded_key
    except Exception as e:
        print(f"Info: Could not get MCP_API_KEY from Kubernetes secret: {e}", file=sys.stderr)
    
    # Try Terraform output as fallback
    try:
        terraform_dir = Path(__file__).parent.parent / "infrastructure"
        result = subprocess.run(
            ["terraform", "output", "-raw", "mcp_api_key"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        key = result.stdout.strip()
        if key:
            print("Info: Retrieved MCP_API_KEY from Terraform output")
            return key
    except Exception as e:
        print(f"Info: Could not get MCP_API_KEY from Terraform: {e}", file=sys.stderr)
    
    print("Warning: Using placeholder MCP_API_KEY - please update manually", file=sys.stderr)
    return "your-secret-key-here"


def wait_for_loadbalancer(service_name: str, timeout: int = 300) -> str:
    """
    Wait for LoadBalancer IP to be assigned.
    
    Args:
        service_name: Name of the service
        timeout: Maximum wait time in seconds
    
    Returns:
        Service IP address or "N/A" if timeout
    """
    import time
    
    print(f"Waiting for LoadBalancer IP for {service_name}...", end="", flush=True)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        ip = get_service_ip(service_name, "loadbalancer")
        if ip != "N/A" and ip:
            print(f" {ip}")
            return ip
        
        print(".", end="", flush=True)
        time.sleep(5)
    
    print(" TIMEOUT")
    return "N/A"


def generate_env_file(wait: bool = True):
    """Generate .env file with service IPs."""
    print("Fetching service IPs from Kubernetes cluster...")
    
    # Get MCP API key
    mcp_api_key = get_mcp_api_key()
    
    # Define services and their IP types
    services = {
        "mcp-chef-services": ("loadbalancer", wait),
        "mcp-public-farmer-tools": ("loadbalancer", wait),
        "mcp-visualization-generator": ("loadbalancer", wait),
        "api-stock": ("clusterip", False),  # ClusterIP doesn't need waiting
    }
    
    # Fetch IPs
    service_ips = {}
    for service_name, (ip_type, should_wait) in services.items():
        if should_wait:
            service_ips[service_name] = wait_for_loadbalancer(service_name)
        else:
            service_ips[service_name] = get_service_ip(service_name, ip_type)
            print(f"{service_name}: {service_ips[service_name]}")
    
    # Generate .env content
    env_content = f"""# Service IPs for deployed services
# Automatically generated by generate_env.py
# Run: uv run generate_env.py

# MCP API Key for authentication
MCP_API_KEY={mcp_api_key}

# Service IPs (LoadBalancer external IPs)
MCP_VISUALIZATION_IP={service_ips['mcp-visualization-generator']}
MCP_PUBLIC_FARMER_IP={service_ips['mcp-public-farmer-tools']}
MCP_CHEF_SERVICES_IP={service_ips['mcp-chef-services']}

# API Services (ClusterIP - for internal access only)
API_STOCK_IP={service_ips['api-stock']}
"""
    
    # Write to .env file
    env_file = Path(__file__).parent / ".env"
    env_file.write_text(env_content)
    
    print(f"\n✅ Generated {env_file}")
    print("\nService IPs:")
    for service_name, ip in service_ips.items():
        print(f"  {service_name}: {ip}")
    
    # Check if any IPs are N/A
    if any(ip == "N/A" for ip in service_ips.values()):
        print("\n⚠️  Warning: Some service IPs are not available (N/A)")
        print("   LoadBalancer IPs may take 1-3 minutes to be assigned by Azure.")
        print("   Run this script again after a few minutes.")
        return False
    
    return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate .env file for tests with Kubernetes service IPs"
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for LoadBalancer IPs, just get current values",
    )
    args = parser.parse_args()
    
    try:
        success = generate_env_file(wait=not args.no_wait)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
