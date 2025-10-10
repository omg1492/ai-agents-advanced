"""Remote integration tests for MCP Chef Services deployed on Azure.

These tests verify the deployed MCP server is accessible and functional.
Uses FastMCP Client with HTTP transport for remote testing.
"""

import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastmcp import Client
import pytest_asyncio

# Load environment variables from project root
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Remote MCP server configuration
REMOTE_MCP_URL = os.getenv("CHEF_SERVICES_MCP_URL", "").rstrip("/")
REMOTE_API_KEY = os.getenv("CHEF_SERVICES_MCP_API_KEY", "")

if not REMOTE_MCP_URL or not REMOTE_API_KEY:
    pytest.skip("Remote MCP configuration not available", allow_module_level=True)


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def remote_client():
    """Create FastMCP Client for remote HTTP server."""
    client = Client(
        REMOTE_MCP_URL,
        auth=REMOTE_API_KEY  # Bearer token authentication
    )
    async with client:
        yield client


# ============================================================================
# Discovery Tests
# ============================================================================

@pytest.mark.asyncio
async def test_remote_discovery(remote_client):
    """Test MCP server discovery endpoint lists all tools."""
    print(f"\n🔍 Testing MCP discovery at {REMOTE_MCP_URL}")
    
    tools = await remote_client.list_tools()
    
    # Should have 5 tools
    assert len(tools) == 5
    
    # Extract tool names
    tool_names = [tool.name for tool in tools]
    
    # Verify all expected tools are present
    expected_tools = [
        "search_chefs",
        "search_services",
        "check_availability",
        "calculate_pricing",
        "place_order"
    ]
    
    for expected in expected_tools:
        assert expected in tool_names, f"Tool {expected} not found in discovery"
    
    print(f"✅ Discovery successful: {len(tools)} tools found")
    print(f"   Tools: {', '.join(tool_names)}")


# ============================================================================
# Tool Invocation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_remote_search_chefs(remote_client):
    """Test search_chefs tool on remote server."""
    print("\n🔍 Testing remote search_chefs")
    
    result = await remote_client.call_tool("search_chefs", {
        "specialty": "Italian",
        "max_results": 3
    })
    
    # Parse result
    chefs = json.loads(result.content[0].text)
    
    # Should return list of chefs
    assert isinstance(chefs, list)
    assert len(chefs) > 0
    assert len(chefs) <= 3
    
    # First result should be Italian chef
    first_chef = chefs[0]
    assert "chef_id" in first_chef
    assert "name" in first_chef
    assert "specialties" in first_chef
    assert any("italian" in s.lower() for s in first_chef["specialties"])
    
    print(f"✅ search_chefs returned {len(chefs)} Italian chefs")
    print(f"   First chef: {first_chef['name']}")


@pytest.mark.asyncio
async def test_remote_search_services(remote_client):
    """Test search_services tool on remote server."""
    print("\n🔍 Testing remote search_services")
    
    result = await remote_client.call_tool("search_services", {
        "service_type": "catering",
        "guest_count": 50,
        "max_results": 3
    })
    
    services = json.loads(result.content[0].text)
    
    # Should return list of services
    assert isinstance(services, list)
    assert len(services) > 0
    
    # Verify service structure
    first_service = services[0]
    assert "service_id" in first_service
    assert "name" in first_service
    assert "type" in first_service
    assert first_service["type"] == "catering"
    assert "base_price_per_person" in first_service
    
    print(f"✅ search_services returned {len(services)} catering services")
    print(f"   First service: {first_service['name']}")


@pytest.mark.asyncio
async def test_remote_check_availability(remote_client):
    """Test check_availability tool on remote server."""
    print("\n🔍 Testing remote check_availability")
    
    # Use a future date
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    result = await remote_client.call_tool("check_availability", {
        "date": future_date,
        "chef_id": "chef_001"
    })
    
    availability = json.loads(result.content[0].text)
    
    # Should return availability info
    assert "available" in availability
    assert "date" in availability
    assert availability["date"] == future_date
    assert "chef_id" in availability
    assert availability["chef_id"] == "chef_001"
    
    print(f"✅ check_availability: date {future_date} available={availability['available']}")


@pytest.mark.asyncio
async def test_remote_calculate_pricing(remote_client):
    """Test calculate_pricing tool on remote server."""
    print("\n🔍 Testing remote calculate_pricing")
    
    result = await remote_client.call_tool("calculate_pricing", {
        "guest_count": 20,
        "chef_id": "chef_001",
        "duration_hours": 4,
        "menu_complexity": "moderate",
        "additional_services": ["wine_pairing"]
    })
    
    pricing = json.loads(result.content[0].text)
    
    # Should return pricing breakdown
    assert "total" in pricing
    assert "base_cost" in pricing
    assert "breakdown" in pricing
    assert isinstance(pricing["breakdown"], list)
    assert pricing["total"] > 0
    
    print(f"✅ calculate_pricing: total=${pricing['total']:.2f}")
    print(f"   Breakdown items: {len(pricing['breakdown'])}")


@pytest.mark.asyncio
async def test_remote_place_order(remote_client):
    """Test place_order tool on remote server."""
    print("\n🔍 Testing remote place_order")
    
    # Use a future date
    future_date = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d")
    
    result = await remote_client.call_tool("place_order", {
        "date": future_date,
        "guest_count": 25,
        "chef_id": "chef_002",
        "duration_hours": 4,
        "menu_notes": "Test order from remote integration test",
        "contact_info": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+1-555-9999"
        }
    })
    
    order = json.loads(result.content[0].text)
    
    # Should return order confirmation
    assert "order_id" in order
    assert "status" in order
    assert order["status"] == "confirmed"
    assert order["order_id"].startswith("ORD_")
    assert "total_cost" in order
    
    print(f"✅ place_order: {order['order_id']} created")
    print(f"   Status: {order['status']}, Total: ${order['total_cost']:.2f}")


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_remote_tool_not_found(remote_client):
    """Test calling non-existent tool returns error."""
    print("\n🔍 Testing invalid tool name")
    
    with pytest.raises(Exception) as exc_info:
        await remote_client.call_tool("non_existent_tool", {})
    
    # Should raise an error
    assert exc_info.value is not None
    
    print("✅ Invalid tool correctly raised error")


@pytest.mark.asyncio
async def test_remote_invalid_arguments(remote_client):
    """Test calling tool with invalid arguments returns error or handles gracefully."""
    print("\n🔍 Testing invalid tool arguments")
    
    result = await remote_client.call_tool("search_chefs", {
        "max_results": -100  # Invalid value
    })
    
    # Tool should handle gracefully and return minimum results
    chefs = json.loads(result.content[0].text)
    
    # Should still return valid results (with clamped max_results)
    assert isinstance(chefs, list)
    
    print("✅ Invalid arguments handled gracefully")


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_remote_response_time(remote_client):
    """Test remote MCP server responds within reasonable time."""
    print("\n🔍 Testing response time")
    
    import time
    
    start = time.time()
    await remote_client.call_tool("search_chefs", {"max_results": 5})
    elapsed = time.time() - start
    
    # Should respond within 5 seconds for simple query
    assert elapsed < 5.0
    
    print(f"✅ Response time: {elapsed:.2f}s")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
