"""Tests for search_services MCP tool.

These tests verify the search_services tool implementation using FastMCP Client pattern.
Tests cover service type filtering, guest count capacity matching, cuisine preferences,
and result sorting.
"""

import pytest
import json
from fastmcp import Client

# Import MCP server
from main import _mcp


# ============================================================================
# Test: Tool Registration
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_tool_registration():
    """Verify that search_services tool is registered with correct schema."""
    
    print("\n🔍 Testing search_services tool registration...")
    
    async with Client(_mcp) as client:
        tools = await client.list_tools()
        
        # Check tool is registered
        tool_names = [tool.name for tool in tools]
        assert "search_services" in tool_names
        
        # Get tool definition
        search_services_tool = next(t for t in tools if t.name == "search_services")
        
        # Verify description exists
        assert search_services_tool.description
        assert "service" in search_services_tool.description.lower()
        
        print("✅ Tool registered successfully")


# ============================================================================
# Test: Service Type Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_by_type_catering():
    """Test search_services filtering by catering type."""
    
    print("\n🔍 Testing search_services with service_type=catering...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {"service_type": "catering"})
        
        # Parse JSON response
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return at least one catering service
        assert len(services) > 0
        
        # All results should be catering type
        for service in services:
            assert service["type"] == "catering"
            assert "service_id" in service
            assert "name" in service
            assert "base_price_per_person" in service
            assert "min_guests" in service
            assert "max_guests" in service
            assert "includes" in service
            assert "description" in service
            assert "match_score" in service
        
        print(f"✅ Found {len(services)} catering services")


@pytest.mark.asyncio
async def test_search_services_by_type_private_chef():
    """Test search_services filtering by private_chef type."""
    
    print("\n🔍 Testing search_services with service_type=private_chef...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {"service_type": "private_chef"})
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return private chef services
        assert len(services) > 0
        
        for service in services:
            assert service["type"] == "private_chef"
        
        print(f"✅ Found {len(services)} private chef services")


@pytest.mark.asyncio
async def test_search_services_by_type_delivery():
    """Test search_services filtering by delivery type."""
    
    print("\n🔍 Testing search_services with service_type=delivery...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {"service_type": "delivery"})
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return delivery services
        assert len(services) > 0
        
        for service in services:
            assert service["type"] == "delivery"
        
        print(f"✅ Found {len(services)} delivery services")


@pytest.mark.asyncio
async def test_search_services_by_type_meal_prep():
    """Test search_services filtering by meal_prep type."""
    
    print("\n🔍 Testing search_services with service_type=meal_prep...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {"service_type": "meal_prep"})
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return meal prep services
        assert len(services) > 0
        
        for service in services:
            assert service["type"] == "meal_prep"
        
        print(f"✅ Found {len(services)} meal prep services")


@pytest.mark.asyncio
async def test_search_services_invalid_type():
    """Test search_services with invalid service type returns empty list."""
    
    print("\n🔍 Testing search_services with invalid service_type...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {"service_type": "invalid_type"})
        
        # Check if content exists (empty result returns no content)
        if not result.content or len(result.content) == 0:
            print("✅ Invalid type correctly returns no content (empty result)")
            return
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return empty list
        assert len(services) == 0
        
        print("✅ Invalid type correctly returns empty list")


# ============================================================================
# Test: Guest Count Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_by_guest_count_small():
    """Test search_services filtering by small guest count."""
    
    print("\n🔍 Testing search_services with guest_count=6 for private_chef...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "private_chef",
            "guest_count": 6
        })
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return services that can accommodate 6 guests
        assert len(services) > 0
        
        for service in services:
            assert service["min_guests"] <= 6 <= service["max_guests"]
        
        print(f"✅ Found {len(services)} services for 6 guests")


@pytest.mark.asyncio
async def test_search_services_by_guest_count_large():
    """Test search_services filtering by large guest count."""
    
    print("\n🔍 Testing search_services with guest_count=150 for catering...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "guest_count": 150
        })
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return catering services that can handle 150 guests
        assert len(services) > 0
        
        for service in services:
            assert service["min_guests"] <= 150 <= service["max_guests"]
        
        print(f"✅ Found {len(services)} catering services for 150 guests")


@pytest.mark.asyncio
async def test_search_services_guest_count_out_of_range():
    """Test search_services with guest count outside all service capacities."""
    
    print("\n🔍 Testing search_services with guest_count=500 (too large)...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "guest_count": 500
        })
        
        # Check if content exists (empty result returns no content)
        if not result.content or len(result.content) == 0:
            print("✅ Correctly returns no content for out-of-range guest count")
            return
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return empty (no services handle 500 guests)
        assert len(services) == 0
        
        print("✅ Correctly returns empty for out-of-range guest count")


# ============================================================================
# Test: Cuisine Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_by_cuisine():
    """Test search_services filtering by cuisine preference."""
    
    print("\n🔍 Testing search_services with cuisine=BBQ...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "cuisine": "BBQ"
        })
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return at least one BBQ-related service
        assert len(services) > 0
        
        # First result should have BBQ in name or description
        first_service = services[0]
        text = (first_service["name"] + " " + first_service["description"]).lower()
        assert "bbq" in text
        
        print(f"✅ Found {len(services)} BBQ catering services")


@pytest.mark.asyncio
async def test_search_services_cuisine_case_insensitive():
    """Test search_services cuisine filtering is case-insensitive."""
    
    print("\n🔍 Testing search_services cuisine case insensitivity...")
    
    async with Client(_mcp) as client:
        result_upper = await client.call_tool("search_services", {
            "service_type": "catering",
            "cuisine": "BBQ"
        })
        result_lower = await client.call_tool("search_services", {
            "service_type": "catering",
            "cuisine": "bbq"
        })
        
        services_upper = json.loads(result_upper.content[0].text)
        services_lower = json.loads(result_lower.content[0].text)
        
        # Should return same results
        assert len(services_upper) == len(services_lower)
        
        ids_upper = [s["service_id"] for s in services_upper]
        ids_lower = [s["service_id"] for s in services_lower]
        assert ids_upper == ids_lower
        
        print("✅ Case-insensitive matching works correctly")


# ============================================================================
# Test: Combined Filters
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_combined_filters():
    """Test search_services with multiple filters combined."""
    
    print("\n🔍 Testing search_services with type + guest_count + cuisine...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "guest_count": 50,
            "cuisine": "wedding"
        })
        
        content = result.content[0]
        services = json.loads(content.text)
        
        # Should return services matching all filters
        assert len(services) > 0
        
        for service in services:
            assert service["type"] == "catering"
            assert service["min_guests"] <= 50 <= service["max_guests"]
        
        # First result should have wedding relevance
        first_service = services[0]
        text = (first_service["name"] + " " + first_service["description"]).lower()
        assert "wedding" in text
        
        print(f"✅ Found {len(services)} matching services")


# ============================================================================
# Test: Max Results
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_max_results():
    """Test search_services respects max_results parameter."""
    
    print("\n🔍 Testing search_services max_results parameter...")
    
    async with Client(_mcp) as client:
        # Request 2 results
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "max_results": 2
        })
        
        services = json.loads(result.content[0].text)
        assert len(services) == 2
        
        # Request 1 result
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "max_results": 1
        })
        
        services = json.loads(result.content[0].text)
        assert len(services) == 1
        
        print("✅ max_results parameter works correctly")


@pytest.mark.asyncio
async def test_search_services_max_results_cap():
    """Test search_services caps max_results at 20."""
    
    print("\n🔍 Testing search_services max_results cap...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "max_results": 100
        })
        
        services = json.loads(result.content[0].text)
        
        # Should be capped (we have fewer than 20 catering services)
        assert len(services) <= 20
        
        print(f"✅ Returned {len(services)} services (capped appropriately)")


# ============================================================================
# Test: Result Sorting
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_sorting():
    """Test search_services results are sorted by relevance."""
    
    print("\n🔍 Testing search_services result sorting...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "guest_count": 50,
            "cuisine": "wedding"
        })
        
        services = json.loads(result.content[0].text)
        
        # Should have multiple results
        assert len(services) > 0
        
        # Verify descending match_score order
        scores = [s["match_score"] for s in services]
        assert scores == sorted(scores, reverse=True)
        
        print(f"✅ Results sorted correctly by match score")


# ============================================================================
# Test: Field Completeness
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_complete_fields():
    """Test search_services returns all expected service fields."""
    
    print("\n🔍 Testing search_services field completeness...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_services", {
            "service_type": "catering",
            "max_results": 1
        })
        
        services = json.loads(result.content[0].text)
        assert len(services) == 1
        
        service = services[0]
        
        # Verify all expected fields
        required_fields = [
            "service_id", "type", "name", "base_price_per_person",
            "min_guests", "max_guests", "includes", "description", "match_score"
        ]
        
        for field in required_fields:
            assert field in service, f"Missing field: {field}"
        
        # Verify field types and content
        assert service["service_id"].startswith("svc_")
        assert service["type"] == "catering"
        assert len(service["name"]) > 0
        assert service["base_price_per_person"] > 0
        assert service["min_guests"] > 0
        assert service["max_guests"] >= service["min_guests"]
        assert isinstance(service["includes"], list)
        assert len(service["includes"]) > 0
        assert len(service["description"]) > 0
        assert service["match_score"] > 0
        
        print("✅ All fields present and valid")


# ============================================================================
# Test: Deterministic Results
# ============================================================================

@pytest.mark.asyncio
async def test_search_services_deterministic():
    """Test search_services returns consistent results for same query."""
    
    print("\n🔍 Testing search_services deterministic behavior...")
    
    async with Client(_mcp) as client:
        # Run same query twice
        result1 = await client.call_tool("search_services", {
            "service_type": "catering",
            "guest_count": 50
        })
        result2 = await client.call_tool("search_services", {
            "service_type": "catering",
            "guest_count": 50
        })
        
        services1 = json.loads(result1.content[0].text)
        services2 = json.loads(result2.content[0].text)
        
        # Should return identical results
        assert len(services1) == len(services2)
        
        for i in range(len(services1)):
            assert services1[i]["service_id"] == services2[i]["service_id"]
            assert services1[i]["match_score"] == services2[i]["match_score"]
        
        print("✅ Deterministic results verified")


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
