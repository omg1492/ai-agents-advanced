"""Tests for calculate_pricing MCP tool.

These tests verify the calculate_pricing tool implementation using FastMCP Client pattern.
Tests cover chef-based pricing, service-based pricing, menu complexity adjustments,
additional services, and error handling.
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
async def test_calculate_pricing_tool_registration():
    """Verify that calculate_pricing tool is registered with correct schema."""
    
    print("\n🔍 Testing calculate_pricing tool registration...")
    
    async with Client(_mcp) as client:
        tools = await client.list_tools()
        
        # Check tool is registered
        tool_names = [tool.name for tool in tools]
        assert "calculate_pricing" in tool_names
        
        # Get tool definition
        tool = next(t for t in tools if t.name == "calculate_pricing")
        
        # Verify description exists
        assert tool.description
        assert "pricing" in tool.description.lower()
        
        print("✅ Tool registered successfully")


# ============================================================================
# Test: Chef-Based Pricing
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_chef_basic():
    """Test calculate_pricing for a chef with basic parameters."""
    
    print("\n🔍 Testing calculate_pricing for chef...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 10,
            "chef_id": "chef_001",
            "duration_hours": 4
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Check response structure
        assert "total" in response
        assert "base_cost" in response
        assert "breakdown" in response
        assert response["chef_id"] == "chef_001"
        assert response["chef_name"] is not None
        
        # Chef pricing = hourly_rate × duration
        # Default complexity is moderate (1.3x)
        assert response["total"] > 0
        assert response["complexity_multiplier"] == 1.3
        assert len(response["breakdown"]) >= 2  # Base + complexity
        
        print(f"✅ Chef pricing calculated: ${response['total']}")


@pytest.mark.asyncio
async def test_calculate_pricing_chef_with_simple_complexity():
    """Test calculate_pricing for chef with simple menu complexity."""
    
    print("\n🔍 Testing chef pricing with simple complexity...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 10,
            "chef_id": "chef_002",
            "duration_hours": 3,
            "menu_complexity": "simple"
        })
        
        response = json.loads(result.content[0].text)
        
        # Simple complexity = 1.0x (no adjustment)
        assert response["menu_complexity"] == "simple"
        assert response["complexity_multiplier"] == 1.0
        
        # Total should equal base cost (no complexity adjustment)
        assert response["total"] == response["base_cost"]
        
        print(f"✅ Simple complexity: ${response['total']}")


@pytest.mark.asyncio
async def test_calculate_pricing_chef_with_complex_complexity():
    """Test calculate_pricing for chef with complex menu complexity."""
    
    print("\n🔍 Testing chef pricing with complex complexity...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 10,
            "chef_id": "chef_003",
            "duration_hours": 5,
            "menu_complexity": "complex"
        })
        
        response = json.loads(result.content[0].text)
        
        # Complex complexity = 1.6x (+60%)
        assert response["menu_complexity"] == "complex"
        assert response["complexity_multiplier"] == 1.6
        
        # Total should be base × 1.6
        expected_total = response["base_cost"] * 1.6
        assert abs(response["total"] - expected_total) < 0.01
        
        print(f"✅ Complex complexity: ${response['total']}")


@pytest.mark.asyncio
async def test_calculate_pricing_invalid_chef():
    """Test calculate_pricing with non-existent chef."""
    
    print("\n🔍 Testing calculate_pricing with invalid chef...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 10,
            "chef_id": "chef_999",
            "duration_hours": 4
        })
        
        response = json.loads(result.content[0].text)
        
        # Should return error
        assert "error" in response
        assert response["error"] == "chef_not_found"
        assert response["total"] == 0
        
        print("✅ Invalid chef correctly rejected")


# ============================================================================
# Test: Service-Based Pricing
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_service_basic():
    """Test calculate_pricing for a service with basic parameters."""
    
    print("\n🔍 Testing calculate_pricing for service...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 50,
            "service_id": "svc_001"
        })
        
        response = json.loads(result.content[0].text)
        
        # Check response structure
        assert response["total"] > 0
        assert response["service_id"] == "svc_001"
        assert response["service_name"] is not None
        
        # Service pricing = per_person_rate × guest_count × complexity
        # Default complexity is moderate (1.3x)
        assert response["complexity_multiplier"] == 1.3
        assert len(response["breakdown"]) >= 2
        
        print(f"✅ Service pricing calculated: ${response['total']}")


@pytest.mark.asyncio
async def test_calculate_pricing_service_guest_count_validation():
    """Test calculate_pricing validates service guest count capacity."""
    
    print("\n🔍 Testing service guest count validation...")
    
    async with Client(_mcp) as client:
        # Try with too few guests (below min_guests)
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 5,
            "service_id": "svc_001"  # Corporate lunch: 10-200 guests
        })
        
        response = json.loads(result.content[0].text)
        
        # Should return error
        assert "error" in response
        assert response["error"] == "guest_count_out_of_range"
        assert response["total"] == 0
        
        print("✅ Guest count validation works correctly")


@pytest.mark.asyncio
async def test_calculate_pricing_invalid_service():
    """Test calculate_pricing with non-existent service."""
    
    print("\n🔍 Testing calculate_pricing with invalid service...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 30,
            "service_id": "svc_999"
        })
        
        response = json.loads(result.content[0].text)
        
        # Should return error
        assert "error" in response
        assert response["error"] == "service_not_found"
        assert response["total"] == 0
        
        print("✅ Invalid service correctly rejected")


# ============================================================================
# Test: Additional Services
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_with_wine_pairing():
    """Test calculate_pricing with wine pairing addon."""
    
    print("\n🔍 Testing pricing with wine pairing...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 20,
            "service_id": "svc_001",  # Corporate lunch: 10-200 guests
            "menu_complexity": "simple",
            "additional_services": ["wine_pairing"]
        })
        
        response = json.loads(result.content[0].text)
        
        # Wine pairing = $15 per person
        assert response["additional_services_cost"] == 15 * 20
        
        # Should have breakdown item for wine pairing
        wine_item = next((b for b in response["breakdown"] if "wine" in b["item"].lower()), None)
        assert wine_item is not None
        assert wine_item["amount"] == 15 * 20
        
        print(f"✅ Wine pairing added: +${response['additional_services_cost']}")


@pytest.mark.asyncio
async def test_calculate_pricing_with_multiple_addons():
    """Test calculate_pricing with multiple additional services."""
    
    print("\n🔍 Testing pricing with multiple addons...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 30,
            "service_id": "svc_001",  # Corporate lunch: 10-200 guests
            "menu_complexity": "moderate",
            "additional_services": [
                "wine_pairing",
                "specialty_dessert",
                "premium_ingredients"
            ]
        })
        
        response = json.loads(result.content[0].text)
        
        # Calculate expected addon cost
        # wine_pairing: $15 × 30 = $450
        # specialty_dessert: $12 × 30 = $360
        # premium_ingredients: $20 × 30 = $600
        # Total addons: $1410
        expected_addons = (15 + 12 + 20) * 30
        assert response["additional_services_cost"] == expected_addons
        
        # Should have 3 addon items in breakdown
        addon_items = [b for b in response["breakdown"] if "Additional" in b["item"]]
        assert len(addon_items) == 3
        
        print(f"✅ Multiple addons: +${response['additional_services_cost']}")


@pytest.mark.asyncio
async def test_calculate_pricing_with_equipment_rental():
    """Test calculate_pricing with equipment rental (flat fee)."""
    
    print("\n🔍 Testing pricing with equipment rental...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 50,
            "service_id": "svc_002",  # Wedding: 50-300 guests
            "menu_complexity": "simple",
            "additional_services": ["equipment_rental"]
        })
        
        response = json.loads(result.content[0].text)
        
        # Equipment rental = $100 flat fee
        assert response["additional_services_cost"] == 100
        
        # Should have breakdown item showing flat fee
        equipment_item = next((b for b in response["breakdown"] if "equipment" in b["item"].lower()), None)
        assert equipment_item is not None
        assert equipment_item["amount"] == 100
        assert "Flat fee" in equipment_item["calculation"]
        
        print("✅ Equipment rental (flat fee) added correctly")


# ============================================================================
# Test: Validation & Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_invalid_guest_count():
    """Test calculate_pricing with invalid guest count."""
    
    print("\n🔍 Testing with invalid guest count...")
    
    async with Client(_mcp) as client:
        # Zero guests
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 0,
            "service_id": "svc_001"
        })
        
        response = json.loads(result.content[0].text)
        
        assert "error" in response
        assert response["error"] == "invalid_guest_count"
        assert response["total"] == 0
        
        # Negative guests
        result2 = await client.call_tool("calculate_pricing", {
            "guest_count": -5,
            "service_id": "svc_001"
        })
        
        response2 = json.loads(result2.content[0].text)
        assert "error" in response2
        assert response2["error"] == "invalid_guest_count"
        
        print("✅ Invalid guest counts rejected")


@pytest.mark.asyncio
async def test_calculate_pricing_missing_pricing_basis():
    """Test calculate_pricing without chef_id or service_id."""
    
    print("\n🔍 Testing without pricing basis...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 20
        })
        
        response = json.loads(result.content[0].text)
        
        # Should return error
        assert "error" in response
        assert response["error"] == "missing_pricing_basis"
        assert response["total"] == 0
        
        print("✅ Missing pricing basis correctly rejected")


@pytest.mark.asyncio
async def test_calculate_pricing_invalid_duration():
    """Test calculate_pricing with invalid duration."""
    
    print("\n🔍 Testing with invalid duration...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 10,
            "chef_id": "chef_001",
            "duration_hours": 0
        })
        
        response = json.loads(result.content[0].text)
        
        assert "error" in response
        assert response["error"] == "invalid_duration"
        assert response["total"] == 0
        
        print("✅ Invalid duration rejected")


# ============================================================================
# Test: Default Values
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_default_duration():
    """Test calculate_pricing uses default duration when not provided."""
    
    print("\n🔍 Testing default duration...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 15,
            "chef_id": "chef_001"
            # duration_hours not provided
        })
        
        response = json.loads(result.content[0].text)
        
        # Should default to 4 hours
        assert response["duration_hours"] == 4
        assert response["total"] > 0
        
        print("✅ Default duration (4 hours) applied")


@pytest.mark.asyncio
async def test_calculate_pricing_default_complexity():
    """Test calculate_pricing uses default complexity when not provided."""
    
    print("\n🔍 Testing default complexity...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 25,
            "service_id": "svc_001"
            # menu_complexity not provided
        })
        
        response = json.loads(result.content[0].text)
        
        # Should default to moderate (1.3x)
        assert response["menu_complexity"] == "moderate"
        assert response["complexity_multiplier"] == 1.3
        
        print("✅ Default complexity (moderate) applied")


@pytest.mark.asyncio
async def test_calculate_pricing_invalid_complexity():
    """Test calculate_pricing handles invalid complexity gracefully."""
    
    print("\n🔍 Testing invalid complexity...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 100,  # svc_002 needs 50-300 guests
            "service_id": "svc_002",
            "menu_complexity": "super_extreme"
        })
        
        response = json.loads(result.content[0].text)
        
        # Should fallback to moderate
        assert response["menu_complexity"] == "moderate"
        assert response["complexity_multiplier"] == 1.3
        
        print("✅ Invalid complexity defaults to moderate")


# ============================================================================
# Test: Breakdown Completeness
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_breakdown_structure():
    """Test calculate_pricing returns complete breakdown."""
    
    print("\n🔍 Testing pricing breakdown structure...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 100,  # svc_002 needs 50-300 guests
            "service_id": "svc_002",
            "menu_complexity": "complex",
            "additional_services": ["wine_pairing", "staff_service"]
        })
        
        response = json.loads(result.content[0].text)
        
        # Verify all required fields
        assert "total" in response
        assert "base_cost" in response
        assert "breakdown" in response
        assert "complexity_multiplier" in response
        assert "additional_services_cost" in response
        
        # Breakdown should have: base + complexity + 2 addons = 4 items
        assert len(response["breakdown"]) == 4
        
        # Each breakdown item should have required fields
        for item in response["breakdown"]:
            assert "item" in item
            assert "calculation" in item
            assert "amount" in item
        
        # Verify calculation correctness
        breakdown_total = sum(item["amount"] for item in response["breakdown"])
        assert abs(breakdown_total - response["total"]) < 0.01
        
        print(f"✅ Complete breakdown with {len(response['breakdown'])} items")


# ============================================================================
# Test: Combined Chef + Service
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_chef_and_service():
    """Test calculate_pricing with both chef and service (service takes precedence)."""
    
    print("\n🔍 Testing pricing with both chef and service...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 6,  # svc_003 is 2-12 guests
            "chef_id": "chef_002",
            "service_id": "svc_003",
            "duration_hours": 6,
            "menu_complexity": "moderate"
        })
        
        response = json.loads(result.content[0].text)
        
        # Service takes precedence, so service pricing should be used
        assert response["service_id"] == "svc_003"
        assert response["service_name"] is not None
        
        # Chef info should still be stored (for reference)
        assert response["chef_id"] == "chef_002"
        
        # Breakdown should use service pricing (per-person, not hourly)
        service_items = [b for b in response["breakdown"] if "guests" in b["calculation"].lower()]
        assert len(service_items) > 0
        
        print("✅ Service takes precedence over chef when both provided")


# ============================================================================
# Test: Response Completeness
# ============================================================================

@pytest.mark.asyncio
async def test_calculate_pricing_response_fields():
    """Test calculate_pricing returns all expected fields."""
    
    print("\n🔍 Testing response field completeness...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("calculate_pricing", {
            "guest_count": 25,
            "chef_id": "chef_001",
            "duration_hours": 5,
            "menu_complexity": "complex"
        })
        
        response = json.loads(result.content[0].text)
        
        # Verify all expected fields
        required_fields = [
            "total", "base_cost", "guest_count", "chef_id", "chef_name",
            "service_id", "service_name", "duration_hours", "menu_complexity",
            "complexity_multiplier", "breakdown", "additional_services_cost"
        ]
        
        for field in required_fields:
            assert field in response, f"Missing field: {field}"
        
        # Verify types
        assert isinstance(response["total"], (int, float))
        assert isinstance(response["base_cost"], (int, float))
        assert isinstance(response["breakdown"], list)
        assert response["total"] > 0
        
        print("✅ All response fields present and valid")


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
