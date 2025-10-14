#!/usr/bin/env python3
"""
Build and push MCP server containers to Azure Container Registry.

This script builds MCP server Docker images using ACR Tasks and pushes them
to the Azure Container Registry. It uses Azure CLI authentication (az login).

Requirements:
- Azure CLI installed and authenticated (run 'az login' first)
- config.yaml file in the same directory as this script
- Registry name in config.yaml must be set by Terraform
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with: pip install pyyaml")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(message: str) -> None:
    """Print a formatted header message."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.OKBLUE}ℹ {message}{Colors.ENDC}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}", file=sys.stderr)


def run_command(
    cmd: list[str],
    check: bool = True,
    capture_output: bool = False,
    cwd: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Run a shell command and handle errors.
    
    Args:
        cmd: Command and arguments as a list
        check: Whether to raise exception on non-zero exit
        capture_output: Whether to capture stdout/stderr
        cwd: Working directory for the command
        
    Returns:
        CompletedProcess object with return code and output
    """
    print_info(f"Running: {' '.join(cmd)}")
    try:
        # On Windows, use shell=True to ensure az.cmd is found
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
            cwd=cwd,
            shell=(sys.platform == "win32")
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        raise


def check_az_cli() -> bool:
    """Check if Azure CLI is installed and user is logged in."""
    try:
        result = run_command(
            ["az", "account", "show"],
            capture_output=True,
            check=False
        )
        if result.returncode == 0:
            account_info = json.loads(result.stdout)
            print_success(f"Azure CLI authenticated as: {account_info.get('user', {}).get('name', 'unknown')}")
            print_info(f"Subscription: {account_info.get('name', 'unknown')} ({account_info.get('id', 'unknown')})")
            return True
        else:
            print_error("Azure CLI not authenticated. Please run 'az login' first.")
            return False
    except FileNotFoundError:
        print_error("Azure CLI not found. Please install it from https://aka.ms/azure-cli")
        return False
    except Exception as e:
        print_error(f"Error checking Azure CLI: {e}")
        return False


def build_and_push_image(
    registry_name: str,
    image_name: str,
    image_tag: str,
    context_path: Path,
    dockerfile: str = "Dockerfile"
) -> bool:
    """
    Build and push a Docker image using ACR Tasks.
    
    Args:
        registry_name: Name of the Azure Container Registry
        image_name: Name for the image (e.g., "mcp-chef-services")
        image_tag: Tag for the image (e.g., "latest")
        context_path: Path to the build context directory
        dockerfile: Name of the Dockerfile (default: "Dockerfile")
        
    Returns:
        True if successful, False otherwise
    """
    print_header(f"Building {image_name}:{image_tag}")
    
    if not context_path.exists():
        print_error(f"Context path does not exist: {context_path}")
        return False
    
    dockerfile_path = context_path / dockerfile
    if not dockerfile_path.exists():
        print_error(f"Dockerfile not found: {dockerfile_path}")
        return False
    
    print_info(f"Context: {context_path}")
    print_info(f"Dockerfile: {dockerfile}")
    print_info(f"Registry: {registry_name}")
    print_info(f"Image: {image_name}:{image_tag}")
    
    try:
        # Build and push using ACR Tasks
        # Note: --file path is relative to the context, not absolute
        cmd = [
            "az", "acr", "build",
            "--registry", registry_name,
            "--image", f"{image_name}:{image_tag}",
            "--file", dockerfile,
            "."  # Context is the current directory
        ]
        
        # Run from the context directory
        run_command(cmd, check=True, cwd=str(context_path))
        print_success(f"Successfully built and pushed {image_name}:{image_tag}")
        return True
        
    except subprocess.CalledProcessError:
        print_error(f"Failed to build and push {image_name}:{image_tag}")
        return False


def load_config(config_path: Path) -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config.yaml file
        
    Returns:
        Configuration dictionary
        
    Raises:
        SystemExit: If config file doesn't exist or is invalid
    """
    if not config_path.exists():
        print_error(f"Configuration file not found: {config_path}")
        print()
        print("Please create a config.yaml file with the following structure:")
        print()
        print("```yaml")
        print("# Azure Container Registry name (managed by Terraform)")
        print("registry: \"your-registry-name\"")
        print()
        print("# Services to build and push")
        print("services:")
        print("  - name: service-name")
        print("    path: ../../../../path/to/service")
        print("    tag: latest")
        print("```")
        print()
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config:
            print_error("Configuration file is empty")
            sys.exit(1)
        
        # Validate required fields
        if 'registry' not in config:
            print_error("Configuration must contain 'registry' field")
            sys.exit(1)
        
        if 'services' not in config or not isinstance(config['services'], list):
            print_error("Configuration must contain 'services' array")
            sys.exit(1)
        
        if not config['services']:
            print_error("Configuration must contain at least one service")
            sys.exit(1)
        
        # Check if registry is placeholder
        if config['registry'] == "PLACEHOLDER_REGISTRY_NAME":
            print_error("Registry name is not configured")
            print_info("Run 'terraform apply' in the infrastructure directory to configure the registry name")
            sys.exit(1)
        
        # Validate each service
        for idx, service in enumerate(config['services']):
            if 'name' not in service:
                print_error(f"Service at index {idx} is missing 'name' field")
                sys.exit(1)
            if 'path' not in service:
                print_error(f"Service '{service['name']}' is missing 'path' field")
                sys.exit(1)
            if 'tag' not in service:
                print_warning(f"Service '{service['name']}' is missing 'tag' field, defaulting to 'latest'")
                service['tag'] = 'latest'
        
        return config
        
    except yaml.YAMLError as e:
        print_error(f"Failed to parse configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        sys.exit(1)


def main():
    """Main entry point for the script."""
    print_header("Azure Container Registry - Build and Push")
    
    # Load configuration
    script_dir = Path(__file__).parent
    config_path = script_dir / "config.yaml"
    config = load_config(config_path)
    
    registry_name = config['registry']
    services = config['services']
    
    print_info(f"Configuration loaded from: {config_path}")
    print_info(f"Registry: {registry_name}")
    print_info(f"Services to build: {len(services)}")
    print()
    
    # Check Azure CLI authentication
    if not check_az_cli():
        sys.exit(1)
    
    # Build and push each service
    results = {}
    for service in services:
        service_name = service['name']
        service_path = script_dir / service['path']
        service_tag = service.get('tag', 'latest')
        
        # Resolve relative path
        service_path = service_path.resolve()
        
        success = build_and_push_image(
            registry_name=registry_name,
            image_name=service_name,
            image_tag=service_tag,
            context_path=service_path
        )
        results[service_name] = success
    
    # Print summary
    print_header("Build Summary")
    
    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)
    
    for service_name, success in results.items():
        if success:
            print_success(f"{service_name}: Built and pushed successfully")
        else:
            print_error(f"{service_name}: Build failed")
    
    print()
    if success_count == total_count:
        print_success(f"All {total_count} service(s) built and pushed successfully!")
        print_info(f"Images available in registry: {registry_name}.azurecr.io")
        return 0
    else:
        print_warning(f"{success_count}/{total_count} service(s) built successfully")
        return 1


if __name__ == "__main__":
    sys.exit(main())
