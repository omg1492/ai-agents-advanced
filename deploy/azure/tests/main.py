"""
Smoke tests for deployed infrastructure services.

Tests connectivity and basic health of all deployed services using LoadBalancer IPs.
Includes MCP-specific tests to verify tool availability.
"""

import os
import sys
import argparse
import asyncio
from typing import List, Tuple, Dict, Optional
from dotenv import load_dotenv
import requests
from colorama import Fore, Style, init
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Initialize colorama for Windows support
init(autoreset=True)


class SmokeTest:
    """Execute smoke tests against deployed services."""

    def __init__(
        self,
        service_ips: Dict[str, str],
        internal_service_ips: Dict[str, str],
        mcp_api_key: Optional[str] = None,
        include_internal: bool = False,
        skip_mcp_tests: bool = False,
    ):
        """
        Initialize smoke test runner.

        Args:
            service_ips: Dictionary mapping external service names to their IP addresses
            internal_service_ips: Dictionary mapping internal service names to their IP addresses
            mcp_api_key: MCP API key for authentication (optional)
            include_internal: Whether to include internal services in tests (default: False)
            skip_mcp_tests: Whether to skip MCP-specific tests (default: False)
        """
        self.service_ips = service_ips
        self.internal_service_ips = internal_service_ips
        self.mcp_api_key = mcp_api_key
        self.include_internal = include_internal
        self.skip_mcp_tests = skip_mcp_tests
        self.results: List[Tuple[str, bool, str]] = []
        self.timeout = 10  # seconds

    def print_header(self):
        """Print test suite header."""
        total_services = len(self.service_ips)
        if self.include_internal:
            total_services += len(self.internal_service_ips)
        
        print("\n" + "=" * 70)
        print(f"{Fore.CYAN}{Style.BRIGHT}🔍 Infrastructure Smoke Tests{Style.RESET_ALL}")
        print("=" * 70)
        print(f"{Fore.WHITE}Testing {total_services} services{Style.RESET_ALL}")
        if self.internal_service_ips and not self.include_internal:
            print(f"{Fore.YELLOW}({len(self.internal_service_ips)} internal service(s) skipped - use --include-internal to test){Style.RESET_ALL}")
        print("=" * 70 + "\n")

    def test_endpoint(self, service_name: str, endpoint: str) -> bool:
        """
        Test a single endpoint for connectivity and health.

        Args:
            service_name: Display name of the service
            endpoint: Full URL to test

        Returns:
            True if test passed, False otherwise
        """
        print(f"Testing {Fore.CYAN}{service_name:<30}{Style.RESET_ALL} ", end="", flush=True)

        try:
            response = requests.get(endpoint, timeout=self.timeout)
            
            if response.status_code == 200:
                print(f"[{Fore.GREEN}✓ PASS{Style.RESET_ALL}] {Fore.GREEN}HTTP {response.status_code}{Style.RESET_ALL}")
                self.results.append((service_name, True, f"HTTP {response.status_code}"))
                return True
            else:
                print(f"[{Fore.RED}✗ FAIL{Style.RESET_ALL}] {Fore.RED}HTTP {response.status_code}{Style.RESET_ALL}")
                self.results.append((service_name, False, f"HTTP {response.status_code}"))
                return False

        except requests.exceptions.Timeout:
            print(f"[{Fore.RED}✗ FAIL{Style.RESET_ALL}] {Fore.RED}Timeout after {self.timeout}s{Style.RESET_ALL}")
            self.results.append((service_name, False, f"Timeout ({self.timeout}s)"))
            return False

        except requests.exceptions.ConnectionError:
            print(f"[{Fore.RED}✗ FAIL{Style.RESET_ALL}] {Fore.RED}Connection error{Style.RESET_ALL}")
            self.results.append((service_name, False, "Connection error"))
            return False

        except Exception as e:
            print(f"[{Fore.RED}✗ FAIL{Style.RESET_ALL}] {Fore.RED}{str(e)[:50]}{Style.RESET_ALL}")
            self.results.append((service_name, False, str(e)[:50]))
            return False

    def run_connectivity_tests(self):
        """Run connectivity tests for all services."""
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}📡 Connectivity Tests{Style.RESET_ALL}\n")
        
        # Test external services
        for service_name, ip_address in self.service_ips.items():
            if not ip_address or ip_address == "N/A":
                print(f"Testing {Fore.CYAN}{service_name:<30}{Style.RESET_ALL} ", end="", flush=True)
                print(f"[{Fore.YELLOW}⊘ SKIP{Style.RESET_ALL}] {Fore.YELLOW}No IP configured{Style.RESET_ALL}")
                self.results.append((service_name, False, "No IP configured"))
                continue
            
            endpoint = f"http://{ip_address}/health"
            self.test_endpoint(service_name, endpoint)
        
        # Test internal services if requested
        if self.include_internal:
            if self.internal_service_ips:
                print(f"\n{Fore.CYAN}Internal Services:{Style.RESET_ALL}\n")
            
            for service_name, ip_address in self.internal_service_ips.items():
                if not ip_address or ip_address == "N/A":
                    print(f"Testing {Fore.CYAN}{service_name:<30}{Style.RESET_ALL} ", end="", flush=True)
                    print(f"[{Fore.YELLOW}⊘ SKIP{Style.RESET_ALL}] {Fore.YELLOW}No IP configured{Style.RESET_ALL}")
                    self.results.append((service_name, False, "No IP configured"))
                    continue
                
                endpoint = f"http://{ip_address}/health"
                self.test_endpoint(service_name, endpoint)

    async def run_mcp_tests(self, mcp_services: Dict[str, str]):
        """Run MCP-specific tests to verify tool availability."""
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}🔌 MCP Protocol Tests{Style.RESET_ALL}\n")
        
        for service_name, ip_address in mcp_services.items():
            if not ip_address or ip_address == "N/A":
                print(f"Testing {Fore.CYAN}{service_name:<30}{Style.RESET_ALL} ", end="", flush=True)
                print(f"[{Fore.YELLOW}⊘ SKIP{Style.RESET_ALL}] {Fore.YELLOW}No IP configured{Style.RESET_ALL}")
                self.results.append((f"{service_name} (MCP)", False, "No IP configured"))
                continue
            
            await self.test_mcp_endpoint(service_name, ip_address)

    async def test_mcp_endpoint(self, service_name: str, ip_address: str):
        """
        Test an MCP endpoint and list available tools.

        Args:
            service_name: Display name of the service
            ip_address: IP address of the MCP server
        """
        print(f"Testing {Fore.CYAN}{service_name:<30}{Style.RESET_ALL} ", end="", flush=True)
        
        try:
            # Construct MCP URL
            mcp_url = f"http://{ip_address}/mcp"
            
            # Create headers with Bearer token authentication
            headers = {}
            if self.mcp_api_key:
                headers["Authorization"] = f"Bearer {self.mcp_api_key}"
            
            # Create StreamableHttpTransport with authentication headers
            transport = StreamableHttpTransport(url=mcp_url, headers=headers)
            client = Client(transport)
            
            # Connect and list tools
            async with client:
                tools = await client.list_tools()
                
                # list_tools() returns a ListToolsResult object with .tools attribute
                # or a list directly depending on the response
                if hasattr(tools, 'tools'):
                    tool_list = tools.tools
                else:
                    tool_list = tools
                
                tool_count = len(tool_list) if tool_list else 0
                
                if tool_count > 0:
                    print(f"[{Fore.GREEN}✓ PASS{Style.RESET_ALL}] {Fore.GREEN}{tool_count} tools available{Style.RESET_ALL}")
                    self.results.append((f"{service_name} (MCP)", True, f"{tool_count} tools"))
                    
                    # Print tool names
                    if tool_list:
                        for tool in tool_list[:5]:  # Show first 5 tools
                            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                            print(f"  {Fore.WHITE}├─ {tool_name}{Style.RESET_ALL}")
                        if tool_count > 5:
                            print(f"  {Fore.WHITE}└─ ... and {tool_count - 5} more{Style.RESET_ALL}")
                else:
                    print(f"[{Fore.YELLOW}⚠ WARN{Style.RESET_ALL}] {Fore.YELLOW}No tools found{Style.RESET_ALL}")
                    self.results.append((f"{service_name} (MCP)", True, "0 tools"))
                    
        except asyncio.TimeoutError:
            print(f"[{Fore.RED}✗ FAIL{Style.RESET_ALL}] {Fore.RED}Timeout{Style.RESET_ALL}")
            self.results.append((f"{service_name} (MCP)", False, "Timeout"))
            
        except Exception as e:
            error_msg = str(e)[:50]
            print(f"[{Fore.RED}✗ FAIL{Style.RESET_ALL}] {Fore.RED}{error_msg}{Style.RESET_ALL}")
            self.results.append((f"{service_name} (MCP)", False, error_msg))

    def print_summary(self):
        """Print test results summary."""
        passed = sum(1 for _, success, _ in self.results if success)
        failed = len(self.results) - passed
        
        print("\n" + "=" * 70)
        print(f"{Fore.CYAN}{Style.BRIGHT}📊 Test Summary{Style.RESET_ALL}")
        print("=" * 70)
        
        if failed == 0:
            print(f"{Fore.GREEN}{Style.BRIGHT}✓ All tests passed!{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Tests completed with some failures{Style.RESET_ALL}")
        
        print(f"\nTotal:  {len(self.results)}")
        print(f"{Fore.GREEN}Passed: {passed}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed: {failed}{Style.RESET_ALL}")
        
        if failed > 0:
            print(f"\n{Fore.RED}{Style.BRIGHT}Failed Tests:{Style.RESET_ALL}")
            for service, success, message in self.results:
                if not success:
                    print(f"  {Fore.RED}✗{Style.RESET_ALL} {service}: {message}")
        
        print("=" * 70 + "\n")
        
        return failed == 0


def main():
    """Execute smoke tests."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Smoke tests for deployed infrastructure services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      # Test external services only
  python main.py --include-internal   # Test both external and internal services
  python main.py --skip-mcp-tests     # Skip MCP protocol tests
        """,
    )
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Include internal (ClusterIP) services in tests",
    )
    parser.add_argument(
        "--skip-mcp-tests",
        action="store_true",
        help="Skip MCP protocol tests (only run health checks)",
    )
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get MCP API key
    mcp_api_key = os.getenv("MCP_API_KEY")
    
    # Define external services (LoadBalancer)
    external_service_ips = {
        "MCP Visualization Generator": os.getenv("MCP_VISUALIZATION_IP", "N/A"),
        "MCP Public Farmer Tools": os.getenv("MCP_PUBLIC_FARMER_IP", "N/A"),
        "MCP Chef Services": os.getenv("MCP_CHEF_SERVICES_IP", "N/A"),
    }
    
    # Define internal services (ClusterIP)
    internal_service_ips = {
        "API Stock Service": os.getenv("API_STOCK_IP", "N/A"),
    }
    
    # Check if any IPs are configured
    all_ips = {**external_service_ips, **internal_service_ips}
    configured_ips = [ip for ip in all_ips.values() if ip != "N/A"]
    if not configured_ips:
        print(f"{Fore.RED}{Style.BRIGHT}ERROR: No service IPs configured in .env file{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Please configure service IPs in .env file.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}See .env.sample for an example.{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}To get LoadBalancer IPs, run:{Style.RESET_ALL}")
        print("  kubectl get svc -o wide")
        print()
        sys.exit(1)
    
    # Run tests
    test_suite = SmokeTest(
        external_service_ips,
        internal_service_ips,
        mcp_api_key,
        include_internal=args.include_internal,
        skip_mcp_tests=args.skip_mcp_tests,
    )
    
    # Run synchronous tests
    test_suite.print_header()
    test_suite.run_connectivity_tests()
    
    # Run async MCP tests if not skipped
    if not args.skip_mcp_tests:
        # Filter MCP services (those with "MCP" in the name)
        mcp_services = {
            name: ip for name, ip in external_service_ips.items()
            if "MCP" in name and ip != "N/A"
        }
        
        if mcp_services:
            asyncio.run(test_suite.run_mcp_tests(mcp_services))
        else:
            print(f"\n{Fore.YELLOW}No MCP services configured for testing{Style.RESET_ALL}\n")
    
    success = test_suite.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
