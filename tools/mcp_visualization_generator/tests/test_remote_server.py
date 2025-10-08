"""
Integration test for remote MCP server deployment.

This test connects to a deployed MCP server via HTTP transport and validates
the generate_infographic tool with real API calls.

Usage:
    python test_remote_server.py --url <SERVER_URL> --api-key <API_KEY>

Example:
    python test_remote_server.py \
        --url https://ca-mcp-viz-gen.grayisland-3e7e5fd0.swedencentral.azurecontainerapps.io/mcp \
        --api-key advancedaiapps2025
"""

import asyncio
import argparse
import json
import sys
from fastmcp import Client


async def test_health_check(base_url: str):
    """Test the health endpoint."""
    import httpx
    
    health_url = base_url.replace("/mcp", "/health")
    print(f"\n🔍 Testing health endpoint: {health_url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(health_url)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print(f"✓ Health check passed: {response.text}")


async def test_generate_visualization(server_url: str, api_key: str):
    """Test the generate_infographic tool via HTTP transport."""
    
    print(f"\n🔍 Connecting to remote MCP server: {server_url}")
    
    # Configure HTTP transport with authentication (bearer token)
    async with Client(server_url, auth=api_key) as client:
        print("✓ Connected to remote MCP server")
        
        # List available tools
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        print(f"✓ Available tools: {tool_names}")
        
        assert "generate_infographic" in tool_names, "generate_infographic tool not found"
        
        # Test: Generate infographic
        print("\n🔍 Testing infographic generation...")
        result = await client.call_tool(
            "generate_infographic",
            {
                "description": "Create a welcome card with the title 'Hello Remote MCP' and a friendly greeting message",
                "style": "card"
            }
        )
        
        print("✓ Tool call completed")
        
        # Check the result
        assert result is not None, "Result is None"
        assert result.content is not None, "Result content is None"
        assert len(result.content) > 0, "Result content is empty"
        
        # Extract HTML from result
        content = result.content[0]
        result_data = json.loads(content.text) if hasattr(content, 'text') else {}
        
        assert result_data.get("type") == "custom_ui", f"Wrong type: {result_data.get('type')}"
        html = result_data.get("html", "")
        assert html.strip().startswith("<!DOCTYPE html>"), "Invalid HTML"
        assert "MCP" in html or "mcp" in html.lower(), "Missing title content"
        
        metadata = result_data.get("metadata", {})
        print(f"\n✓ Generated HTML: {len(html)} characters")
        print(f"✓ Generator: {metadata.get('generator')}")
        print(f"✓ Model: {metadata.get('model')}")
        print(f"\nHTML preview (first 300 chars):\n{html[:300]}...")
        
        return html


async def test_with_data(server_url: str, api_key: str):
    """Test generation with structured data."""
    
    print("\n🔍 Testing generation with structured data...")
    
    async with Client(server_url, auth=api_key) as client:
        result = await client.call_tool(
            "generate_infographic",
            {
                "description": "Create a statistics dashboard showing user metrics",
                "data": {
                    "total_users": 1250,
                    "active_today": 342,
                    "growth_rate": "+12.5%"
                },
                "style": "dashboard"
            }
        )
        
        content = result.content[0]
        result_data = json.loads(content.text) if hasattr(content, 'text') else {}
        html = result_data.get("html", "")
        
        # Verify data appears in HTML
        assert "1250" in html or "1,250" in html, "Missing users data"
        assert "342" in html, "Missing active data"
        assert "12.5" in html, "Missing growth rate"
        
        print(f"✓ Generated HTML: {len(html)} characters")
        print("✓ All data values verified in HTML")
        
        return html


async def test_error_handling(server_url: str, api_key: str):
    """Test error handling with invalid inputs."""
    
    print("\n🔍 Testing error handling...")
    
    async with Client(server_url, auth=api_key) as client:
        # Test with empty description
        try:
            result = await client.call_tool(
                "generate_infographic",
                {
                    "description": "",
                    "style": "card"
                }
            )
            # Check if error is returned
            content = result.content[0]
            result_data = json.loads(content.text) if hasattr(content, 'text') else {}
            if result_data.get("error"):
                print(f"✓ Empty description correctly rejected: {result_data.get('error')}")
            else:
                print("⚠ Empty description was accepted (unexpected)")
        except Exception as e:
            print(f"✓ Empty description correctly rejected with exception: {e}")


async def run_all_tests(server_url: str, api_key: str):
    """Run all tests against the remote server."""
    
    print("=" * 80)
    print("Starting Remote MCP Server Integration Tests")
    print(f"Server URL: {server_url}")
    print("=" * 80)
    
    try:
        # Test health endpoint
        await test_health_check(server_url)
        
        # Run visualization tests
        await test_generate_visualization(server_url, api_key)
        await test_with_data(server_url, api_key)
        await test_error_handling(server_url, api_key)
        
        print("\n" + "=" * 80)
        print("✅ ALL REMOTE TESTS PASSED")
        print("=" * 80)
        return 0
    except AssertionError as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST ASSERTION FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Test remote MCP Visualization Generator server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--url",
        required=True,
        help="MCP server URL (e.g., https://example.com/mcp)"
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for authentication"
    )
    
    args = parser.parse_args()
    
    # Run tests
    exit_code = asyncio.run(run_all_tests(args.url, args.api_key))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
