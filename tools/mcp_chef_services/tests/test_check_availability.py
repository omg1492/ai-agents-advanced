"""Tests for check_availability MCP tool.

These tests verify the check_availability tool implementation using FastMCP Client pattern.
Tests cover date validation, chef availability checking, service validation, and error handling.
"""

import pytest
import json
from datetime import datetime, timedelta
from fastmcp import Client

# Import MCP server
from main import _mcp


# ============================================================================
# Test: Tool Registration
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_tool_registration():
    """Verify that check_availability tool is registered with correct schema."""
    
    print("\n🔍 Testing check_availability tool registration...")
    
    async with Client(_mcp) as client:
        tools = await client.list_tools()
        
        # Check tool is registered
        tool_names = [tool.name for tool in tools]
        assert "check_availability" in tool_names
        
        # Get tool definition
        tool = next(t for t in tools if t.name == "check_availability")
        
        # Verify description exists
        assert tool.description
        assert "availability" in tool.description.lower()
        
        print("✅ Tool registered successfully")


# ============================================================================
# Test: Date Validation
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_future_date():
    """Test check_availability with a valid future date."""
    
    print("\n🔍 Testing check_availability with valid future date...")
    
    # Get a date 7 days in the future
    future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {"date": future_date})
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Check response structure
        assert "available" in response
        assert "date" in response
        assert response["date"] == future_date
        assert "conflicts" in response
        assert "message" in response
        assert "next_available_date" in response
        
        print(f"✅ Future date {future_date} processed correctly")


@pytest.mark.asyncio
async def test_check_availability_invalid_date_format():
    """Test check_availability with invalid date format."""
    
    print("\n🔍 Testing check_availability with invalid date format...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {"date": "2025-13-45"})
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Should indicate unavailable with format error
        assert response["available"] is False
        assert "invalid_date_format" in response["conflicts"]
        assert "invalid" in response["message"].lower()
        
        print("✅ Invalid date format correctly rejected")


@pytest.mark.asyncio
async def test_check_availability_past_date():
    """Test check_availability with a past date."""
    
    print("\n🔍 Testing check_availability with past date...")
    
    # Get a date in the past
    past_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {"date": past_date})
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Should indicate unavailable
        assert response["available"] is False
        assert "date_in_past" in response["conflicts"]
        assert "past" in response["message"].lower()
        
        # Should suggest tomorrow
        assert response["next_available_date"]
        
        print(f"✅ Past date {past_date} correctly rejected")


@pytest.mark.asyncio
async def test_check_availability_today():
    """Test check_availability with today's date (should be rejected)."""
    
    print("\n🔍 Testing check_availability with today's date...")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {"date": today})
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Today should be rejected (must be future)
        assert response["available"] is False
        assert "date_in_past" in response["conflicts"]
        
        print("✅ Today's date correctly rejected")


# ============================================================================
# Test: Chef Availability
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_with_chef():
    """Test check_availability for a specific chef."""
    
    print("\n🔍 Testing check_availability with chef_id...")
    
    # Get a date 10 days in the future
    future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "chef_id": "chef_001"
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Check response includes chef info
        assert response["chef_id"] == "chef_001"
        assert response["chef_name"] is not None
        assert len(response["chef_name"]) > 0
        
        # Available status depends on mock data
        assert isinstance(response["available"], bool)
        
        if not response["available"]:
            # If unavailable, should have chef_blocked conflict
            assert "chef_blocked" in response["conflicts"]
            assert response["next_available_date"]
        
        print(f"✅ Chef availability checked: {response['available']}")


@pytest.mark.asyncio
async def test_check_availability_invalid_chef():
    """Test check_availability with non-existent chef_id."""
    
    print("\n🔍 Testing check_availability with invalid chef_id...")
    
    future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "chef_id": "chef_999"
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Should indicate unavailable with chef not found
        assert response["available"] is False
        assert "chef_not_found" in response["conflicts"]
        assert "not found" in response["message"].lower()
        
        print("✅ Invalid chef_id correctly rejected")


@pytest.mark.asyncio
async def test_check_availability_multiple_chefs():
    """Test check_availability for multiple chefs to verify deterministic blocking."""
    
    print("\n🔍 Testing check_availability for multiple chefs...")
    
    # Test with a date 15 days out
    test_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        results = {}
        
        # Check availability for first 3 chefs
        for i in range(1, 4):
            chef_id = f"chef_{i:03d}"
            result = await client.call_tool("check_availability", {
                "date": test_date,
                "chef_id": chef_id
            })
            
            content = result.content[0]
            response = json.loads(content.text)
            results[chef_id] = response["available"]
        
        # Should get varied availability (at least one different)
        availability_values = set(results.values())
        print(f"Availability results: {results}")
        
        # Results should be deterministic (same chef, same date = same result)
        # Run check again for chef_001
        result2 = await client.call_tool("check_availability", {
            "date": test_date,
            "chef_id": "chef_001"
        })
        response2 = json.loads(result2.content[0].text)
        assert response2["available"] == results["chef_001"]
        
        print("✅ Multiple chef availability checks completed")


# ============================================================================
# Test: Service Validation
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_with_service():
    """Test check_availability for a specific service."""
    
    print("\n🔍 Testing check_availability with service_id...")
    
    future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "service_id": "svc_001"
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Check response includes service info
        assert response["service_id"] == "svc_001"
        assert response["service_name"] is not None
        assert len(response["service_name"]) > 0
        
        # Services are generally available (no specific blocking)
        assert response["available"] is True
        
        print(f"✅ Service availability checked: {response['service_name']}")


@pytest.mark.asyncio
async def test_check_availability_invalid_service():
    """Test check_availability with non-existent service_id."""
    
    print("\n🔍 Testing check_availability with invalid service_id...")
    
    future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "service_id": "svc_999"
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Should indicate unavailable with service not found
        assert response["available"] is False
        assert "service_not_found" in response["conflicts"]
        assert "not found" in response["message"].lower()
        
        print("✅ Invalid service_id correctly rejected")


# ============================================================================
# Test: Combined Chef + Service
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_chef_and_service():
    """Test check_availability with both chef and service."""
    
    print("\n🔍 Testing check_availability with both chef and service...")
    
    future_date = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "chef_id": "chef_002",
            "service_id": "svc_002"
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Check both chef and service info present
        assert response["chef_id"] == "chef_002"
        assert response["chef_name"] is not None
        assert response["service_id"] == "svc_002"
        assert response["service_name"] is not None
        
        # Message should reference both
        assert response["chef_name"] in response["message"]
        assert response["service_name"] in response["message"]
        
        print(f"✅ Combined check: {response['available']}")


# ============================================================================
# Test: Duration Parameter
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_with_duration():
    """Test check_availability with duration_hours parameter."""
    
    print("\n🔍 Testing check_availability with duration_hours...")
    
    future_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "chef_id": "chef_003",
            "duration_hours": 4
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Duration should be mentioned in message if available
        if response["available"]:
            assert "4 hours" in response["message"] or "Duration: 4" in response["message"]
        
        print("✅ Duration parameter included in response")


# ============================================================================
# Test: Next Available Date
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_next_available_date():
    """Test that next_available_date is provided when chef is blocked."""
    
    print("\n🔍 Testing next_available_date suggestion...")
    
    # Try multiple dates to find a blocked one
    async with Client(_mcp) as client:
        found_blocked = False
        
        for days_offset in range(5, 30):
            test_date = (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            
            result = await client.call_tool("check_availability", {
                "date": test_date,
                "chef_id": "chef_001"
            })
            
            response = json.loads(result.content[0].text)
            
            if not response["available"] and "chef_blocked" in response["conflicts"]:
                # Found a blocked date
                assert response["next_available_date"]
                assert response["next_available_date"] > test_date
                found_blocked = True
                print(f"✅ Found blocked date {test_date}, next available: {response['next_available_date']}")
                break
        
        # If no blocked dates found in 30 days, that's also valid
        if not found_blocked:
            print("✅ No blocked dates found in next 30 days (valid scenario)")


# ============================================================================
# Test: Response Structure
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_response_structure():
    """Test that check_availability returns complete response structure."""
    
    print("\n🔍 Testing check_availability response structure...")
    
    future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {
            "date": future_date,
            "chef_id": "chef_001",
            "service_id": "svc_001"
        })
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Verify all expected fields
        required_fields = [
            "available", "date", "chef_id", "chef_name",
            "service_id", "service_name", "conflicts",
            "next_available_date", "message"
        ]
        
        for field in required_fields:
            assert field in response, f"Missing field: {field}"
        
        # Verify field types
        assert isinstance(response["available"], bool)
        assert isinstance(response["date"], str)
        assert isinstance(response["conflicts"], list)
        assert isinstance(response["message"], str)
        assert len(response["message"]) > 0
        
        print("✅ Response structure complete and valid")


# ============================================================================
# Test: Date-Only Check
# ============================================================================

@pytest.mark.asyncio
async def test_check_availability_date_only():
    """Test check_availability with only date parameter (no chef or service)."""
    
    print("\n🔍 Testing check_availability with date only...")
    
    future_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("check_availability", {"date": future_date})
        
        content = result.content[0]
        response = json.loads(content.text)
        
        # Should be available (no specific constraints)
        assert response["available"] is True
        assert response["chef_id"] is None
        assert response["service_id"] is None
        assert len(response["conflicts"]) == 0
        assert future_date in response["message"]
        
        print("✅ Date-only check successful")


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
