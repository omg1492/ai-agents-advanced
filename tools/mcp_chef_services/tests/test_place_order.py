"""Tests for place_order MCP tool.

These tests verify the place_order tool implementation using FastMCP Client pattern.
Tests cover order creation, validation, availability checking, pricing integration,
and date blocking.
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
async def test_place_order_tool_registration():
    """Verify that place_order tool is registered with correct schema."""
    
    print("\n🔍 Testing place_order tool registration...")
    
    async with Client(_mcp) as client:
        tools = await client.list_tools()
        
        # Check tool is registered
        tool_names = [tool.name for tool in tools]
        assert "place_order" in tool_names
        
        # Get tool definition
        place_order_tool = next(t for t in tools if t.name == "place_order")
        
        # Verify description exists
        assert place_order_tool.description
        assert "order" in place_order_tool.description.lower()
        
        print("✅ Tool registered successfully")


# ============================================================================
# Test: Happy Path Orders
# ============================================================================

@pytest.mark.asyncio
async def test_place_order_chef_basic():
    """Test place_order with chef ID."""
    
    print("\n🔍 Testing basic chef order...")
    
    # Use a future date
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 25,
            "chef_id": "chef_001",
            "duration_hours": 5,
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        # Verify success
        assert response["status"] == "confirmed"
        assert response["order_id"] is not None
        assert response["order_id"].startswith("ORD_")
        
        # Verify chef info
        assert response["chef_id"] == "chef_001"
        assert response["chef_name"] is not None
        
        # Verify pricing included
        assert response["total_cost"] > 0
        assert len(response["breakdown"]) > 0
        
        # Verify contact info preserved
        assert response["contact"]["name"] == "John Doe"
        assert response["contact"]["email"] == "john@example.com"
        
        # Verify timestamps
        assert response["created_at"] is not None
        
        print(f"✅ Order created: {response['order_id']}, Total: ${response['total_cost']}")


@pytest.mark.asyncio
async def test_place_order_service_basic():
    """Test place_order with service ID."""
    
    print("\n🔍 Testing basic service order...")
    
    future_date = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 80,
            "service_id": "svc_002",  # Wedding: 50-300 guests
            "contact_info": {
                "name": "Jane Smith",
                "email": "jane@example.com",
                "phone": "555-5678"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        # Verify success
        assert response["status"] == "confirmed"
        assert response["order_id"] is not None
        
        # Verify service info
        assert response["service_id"] == "svc_002"
        assert response["service_name"] is not None
        
        # Verify pricing
        assert response["total_cost"] > 0
        
        print(f"✅ Service order created: {response['order_id']}")


@pytest.mark.asyncio
async def test_place_order_with_menu_notes():
    """Test place_order with menu notes and additional services."""
    
    print("\n🔍 Testing order with menu notes...")
    
    future_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 30,
            "service_id": "svc_001",  # Corporate: 10-200 guests
            "menu_complexity": "complex",
            "additional_services": ["wine_pairing", "equipment_rental"],
            "menu_notes": "Vegetarian and gluten-free options required",
            "contact_info": {
                "name": "Alice Johnson",
                "email": "alice@example.com",
                "phone": "555-9999"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "confirmed"
        assert response["menu_notes"] == "Vegetarian and gluten-free options required"
        
        # Verify additional services in breakdown
        wine_item = any("wine" in b["item"].lower() for b in response["breakdown"])
        equipment_item = any("equipment" in b["item"].lower() for b in response["breakdown"])
        assert wine_item or equipment_item
        
        print(f"✅ Order with menu notes: {response['order_id']}")


@pytest.mark.asyncio
async def test_place_order_sequential_ids():
    """Test place_order generates sequential order IDs."""
    
    print("\n🔍 Testing sequential order IDs...")
    
    async with Client(_mcp) as client:
        # Place multiple orders
        order_ids = []
        
        for i in range(3):
            future_date = (datetime.now() + timedelta(days=70 + i)).strftime("%Y-%m-%d")
            
            result = await client.call_tool("place_order", {
                "date": future_date,
                "guest_count": 20,
                "chef_id": "chef_003",
                "duration_hours": 4,
                "contact_info": {
                    "name": f"Customer {i}",
                    "email": f"customer{i}@example.com",
                    "phone": f"555-000{i}"
                }
            })
            
            response = json.loads(result.content[0].text)
            if response["status"] == "confirmed":
                order_ids.append(response["order_id"])
        
        # Verify we got multiple orders
        assert len(order_ids) >= 2
        
        # Verify IDs are sequential (extract counter from ORD_YYYYMMDD_NNN)
        counters = [int(oid.split("_")[-1]) for oid in order_ids]
        for i in range(len(counters) - 1):
            assert counters[i+1] > counters[i], "Order IDs should be sequential"
        
        print(f"✅ Sequential IDs verified: {order_ids}")


# ============================================================================
# Test: Validation & Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_place_order_missing_contact_info():
    """Test place_order rejects missing contact_info."""
    
    print("\n🔍 Testing missing contact info validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        # FastMCP schema validation should catch this as a ToolError
        with pytest.raises(Exception) as exc_info:
            await client.call_tool("place_order", {
                "date": future_date,
                "guest_count": 20,
                "chef_id": "chef_001",
                "duration_hours": 4
                # Missing contact_info
            })
        
        # Verify it's a validation error about contact_info
        assert "contact_info" in str(exc_info.value).lower()
        print("✅ Missing contact_info correctly rejected by schema validation")



@pytest.mark.asyncio
async def test_place_order_incomplete_contact_info():
    """Test place_order rejects incomplete contact_info."""
    
    print("\n🔍 Testing incomplete contact info validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 20,
            "chef_id": "chef_001",
            "duration_hours": 4,
            "contact_info": {
                "name": "John Doe"
                # Missing email and phone
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "missing_contact_fields" in response.get("error", "")
        
        print("✅ Incomplete contact info rejected")


@pytest.mark.asyncio
async def test_place_order_missing_booking_basis():
    """Test place_order requires either chef_id or service_id."""
    
    print("\n🔍 Testing missing booking basis validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 20,
            "duration_hours": 4,
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
            # Missing both chef_id and service_id
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "missing_booking_basis" in response.get("error", "")
        
        print("✅ Missing booking basis rejected")


@pytest.mark.asyncio
async def test_place_order_invalid_guest_count():
    """Test place_order rejects invalid guest counts."""
    
    print("\n🔍 Testing invalid guest count validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 0,  # Invalid
            "chef_id": "chef_001",
            "duration_hours": 4,
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "invalid_guest_count" in response.get("error", "")
        
        print("✅ Invalid guest count rejected")


@pytest.mark.asyncio
async def test_place_order_invalid_date_format():
    """Test place_order rejects invalid date formats."""
    
    print("\n🔍 Testing invalid date format validation...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": "2025/12/25",  # Wrong format
            "guest_count": 20,
            "chef_id": "chef_001",
            "duration_hours": 4,
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "invalid_date_format" in response.get("error", "")
        
        print("✅ Invalid date format rejected")


@pytest.mark.asyncio
async def test_place_order_past_date():
    """Test place_order rejects past dates."""
    
    print("\n🔍 Testing past date validation...")
    
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": past_date,
            "guest_count": 20,
            "chef_id": "chef_001",
            "duration_hours": 4,
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "past_date" in response.get("error", "")
        
        print("✅ Past date rejected")


@pytest.mark.asyncio
async def test_place_order_invalid_chef():
    """Test place_order rejects invalid chef IDs."""
    
    print("\n🔍 Testing invalid chef ID validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 20,
            "chef_id": "chef_999",  # Invalid
            "duration_hours": 4,
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "chef_not_found" in response.get("error", "")
        
        print("✅ Invalid chef ID rejected")


@pytest.mark.asyncio
async def test_place_order_invalid_service():
    """Test place_order rejects invalid service IDs."""
    
    print("\n🔍 Testing invalid service ID validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 50,
            "service_id": "svc_999",  # Invalid
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "service_not_found" in response.get("error", "")
        
        print("✅ Invalid service ID rejected")


@pytest.mark.asyncio
async def test_place_order_guest_count_out_of_range():
    """Test place_order validates service capacity."""
    
    print("\n🔍 Testing service capacity validation...")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 500,  # svc_002 max is 300
            "service_id": "svc_002",
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        assert response["status"] == "error"
        assert "guest_count_out_of_range" in response.get("error", "")
        
        print("✅ Service capacity validated")


# ============================================================================
# Test: Availability Integration
# ============================================================================

@pytest.mark.asyncio
async def test_place_order_date_unavailable():
    """Test place_order respects chef availability (requires known blocked date)."""
    
    print("\n🔍 Testing unavailable date handling...")
    
    # First, check availability to find a blocked date
    async with Client(_mcp) as client:
        # Try to find a blocked date for chef_001
        test_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        
        avail_result = await client.call_tool("check_availability", {
            "date": test_date,
            "chef_id": "chef_001"
        })
        
        avail_response = json.loads(avail_result.content[0].text)
        
        # If this date is blocked, try to place an order
        if not avail_response.get("available", True):
            order_result = await client.call_tool("place_order", {
                "date": test_date,
                "guest_count": 20,
                "chef_id": "chef_001",
                "duration_hours": 4,
                "contact_info": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "555-1234"
                }
            })
            
            order_response = json.loads(order_result.content[0].text)
            
            # Should be rejected
            assert order_response["status"] == "error"
            assert "date_unavailable" in order_response.get("error", "")
            
            # Should suggest next available date
            assert "next_available_date" in order_response
            
            print(f"✅ Blocked date rejected, suggested: {order_response.get('next_available_date')}")
        else:
            print("⚠️  Skipped (no blocked dates in test range)")


@pytest.mark.asyncio
async def test_place_order_blocks_date():
    """Test place_order blocks the date after successful booking."""
    
    print("\n🔍 Testing date blocking after order...")
    
    # Find a date far in the future that's likely available
    future_date = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        # Check availability before
        avail_before = await client.call_tool("check_availability", {
            "date": future_date,
            "chef_id": "chef_005"
        })
        
        before_response = json.loads(avail_before.content[0].text)
        
        # Only proceed if date is available
        if before_response.get("available", False):
            # Place order
            order_result = await client.call_tool("place_order", {
                "date": future_date,
                "guest_count": 15,
                "chef_id": "chef_005",
                "duration_hours": 4,
                "contact_info": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "phone": "555-0000"
                }
            })
            
            order_response = json.loads(order_result.content[0].text)
            
            if order_response["status"] == "confirmed":
                # Check availability after
                avail_after = await client.call_tool("check_availability", {
                    "date": future_date,
                    "chef_id": "chef_005"
                })
                
                after_response = json.loads(avail_after.content[0].text)
                
                # Date should now be blocked
                assert not after_response.get("available", True)
                assert "conflicts" in after_response
                
                print("✅ Date successfully blocked after order")
            else:
                print("⚠️  Order failed, cannot test blocking")
        else:
            print("⚠️  Skipped (date already blocked)")


# ============================================================================
# Test: Response Structure
# ============================================================================

@pytest.mark.asyncio
async def test_place_order_response_fields():
    """Test place_order returns complete response structure."""
    
    print("\n🔍 Testing response structure...")
    
    future_date = (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("place_order", {
            "date": future_date,
            "guest_count": 40,
            "service_id": "svc_001",
            "menu_complexity": "moderate",
            "contact_info": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "555-1111"
            }
        })
        
        response = json.loads(result.content[0].text)
        
        # Verify all required fields present (success or error)
        assert "order_id" in response
        assert "status" in response
        assert "date" in response
        assert "guest_count" in response
        assert "total_cost" in response
        assert "breakdown" in response
        assert "contact" in response
        assert "created_at" in response
        
        if response["status"] == "confirmed":
            # Success-specific fields
            assert response["order_id"] is not None
            assert response["total_cost"] > 0
            assert len(response["breakdown"]) > 0
            assert response["created_at"] is not None
        
        print("✅ Response structure complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
