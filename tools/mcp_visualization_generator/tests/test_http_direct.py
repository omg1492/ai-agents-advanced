"""
Simple HTTP test for MCP server (direct JSON-RPC calls).

This bypasses the MCP SDK client and tests the server directly with HTTP requests.
"""

import asyncio
import httpx
import json


async def test_mcp_via_http():
    """Test MCP server using direct HTTP JSON-RPC calls."""
    
    base_url = "http://mcp-visualization-generator.4.223.98.178.nip.io"
    api_key = "xizswsf2DCMXeOdSL31xcXcAtc33ZdgB"
    
    async with httpx.AsyncClient() as client:
        # Test health endpoint
        print(f"\n🔍 Testing health endpoint: {base_url}/health")
        response = await client.get(f"{base_url}/health")
        assert response.status_code == 200
        print(f"✓ Health check passed: {response.text}")
        
        # Test MCP initialize
        print(f"\n🔍 Testing MCP initialize: {base_url}/mcp")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = await client.post(
            f"{base_url}/mcp",
            json=init_request,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✓ MCP initialize succeeded")
            result = response.json()
            print(f"Server info: {result.get('result', {}).get('serverInfo', {})}")
        else:
            print(f"❌ MCP initialize failed: {response.status_code}")
            print(f"Response: {response.text}")
        
        # Test list_tools
        print(f"\n🔍 Testing MCP list_tools")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = await client.post(
            f"{base_url}/mcp",
            json=list_tools_request,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            tools = result.get("result", {}).get("tools", [])
            tool_names = [t.get("name") for t in tools]
            print(f"✓ Available tools: {tool_names}")
        else:
            print(f"❌ list_tools failed: {response.status_code}")
            print(f"Response: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_mcp_via_http())
