"""
Integration test using FastMCP in-memory client.

This test connects directly to the MCP server instance (no network/process overhead)
and validates the search_chefs tool with mock data.
"""

import asyncio
import json
import sys
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables before importing main
load_dotenv(Path(__file__).parent.parent / ".env")

# Import after path setup and env loading
from fastmcp import Client
from main import build_server

# Get MCP server instance
_mcp, _ = build_server()


@pytest.mark.asyncio
async def test_search_chefs_tool_registration():
    """Test that search_chefs tool is registered with correct schema."""
    
    print("Connecting to MCP server (in-memory)...")
    
    async with Client(_mcp) as client:
        print("✓ Connected to MCP server")
        
        # List available tools
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        print(f"✓ Available tools: {tool_names}")
        
        assert "search_chefs" in tool_names, "search_chefs tool not found"
        
        # Get tool details
        search_chefs_tool = next(t for t in tools if t.name == "search_chefs")
        assert search_chefs_tool.description
        assert "chef" in search_chefs_tool.description.lower()
        
        print(f"✓ Tool description: {search_chefs_tool.description[:100]}...")


@pytest.mark.asyncio
async def test_search_chefs_no_filters():
    """Test search_chefs with no filters returns default results."""
    
    print("\n🔍 Testing search_chefs with no filters...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {})
        
        print("✓ Tool call completed")
        
        # Parse result
        assert result is not None
        assert result.content is not None
        assert len(result.content) > 0
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Should return default max (5 chefs)
        assert len(chefs) == 5, f"Expected 5 chefs, got {len(chefs)}"
        
        # Verify structure
        for chef in chefs:
            assert "chef_id" in chef
            assert "name" in chef
            assert "specialties" in chef
            assert "experience_years" in chef
            assert "rate_per_hour" in chef
            assert "bio" in chef
            assert "certifications" in chef
            assert "match_score" in chef
        
        print(f"✓ Returned {len(chefs)} chefs with correct structure")
        print(f"✓ First chef: {chefs[0]['name']} ({chefs[0]['chef_id']})")


@pytest.mark.asyncio
async def test_search_chefs_by_specialty_italian():
    """Test search_chefs filtering by Italian specialty."""
    
    print("\n🔍 Testing search_chefs with specialty filter (Italian)...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {"specialty": "Italian"})
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Should return at least one chef
        assert len(chefs) > 0, "Expected at least one Italian chef"
        
        # First result should be Italian specialist
        first_chef = chefs[0]
        assert any("italian" in s.lower() for s in first_chef["specialties"]), \
            f"Expected Italian specialty, got {first_chef['specialties']}"
        
        # Should have high match score
        assert first_chef["match_score"] >= 10, \
            f"Expected high match score, got {first_chef['match_score']}"
        
        print(f"✓ Found {len(chefs)} Italian chef(s)")
        print(f"✓ Top match: {first_chef['name']} (score: {first_chef['match_score']})")
        print(f"✓ Specialties: {', '.join(first_chef['specialties'])}")


@pytest.mark.asyncio
async def test_search_chefs_by_specialty_vegan():
    """Test search_chefs filtering by vegan/vegetarian specialty."""
    
    print("\n🔍 Testing search_chefs with specialty filter (vegan)...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {"specialty": "vegan"})
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Should return vegan/vegetarian specialist
        assert len(chefs) > 0, "Expected at least one vegan chef"
        
        first_chef = chefs[0]
        specialties_lower = [s.lower() for s in first_chef["specialties"]]
        assert any("vegan" in s or "vegetarian" in s for s in specialties_lower), \
            f"Expected vegan/vegetarian specialty, got {first_chef['specialties']}"
        
        print(f"✓ Found {len(chefs)} vegan/vegetarian chef(s)")
        print(f"✓ Top match: {first_chef['name']}")


@pytest.mark.asyncio
async def test_search_chefs_case_insensitive():
    """Test search_chefs specialty filtering is case-insensitive."""
    
    print("\n🔍 Testing case-insensitive specialty filtering...")
    
    async with Client(_mcp) as client:
        result_upper = await client.call_tool("search_chefs", {"specialty": "ITALIAN"})
        result_lower = await client.call_tool("search_chefs", {"specialty": "italian"})
        result_mixed = await client.call_tool("search_chefs", {"specialty": "ItAlIaN"})
        
        # Parse all results
        chefs_upper = json.loads(result_upper.content[0].text)
        chefs_lower = json.loads(result_lower.content[0].text)
        chefs_mixed = json.loads(result_mixed.content[0].text)
        
        # Extract chef IDs
        ids_upper = [c["chef_id"] for c in chefs_upper]
        ids_lower = [c["chef_id"] for c in chefs_lower]
        ids_mixed = [c["chef_id"] for c in chefs_mixed]
        
        # Should all match
        assert ids_upper == ids_lower == ids_mixed, "Case-insensitive matching failed"
        
        print(f"✓ All case variations returned same {len(ids_upper)} chef(s)")


@pytest.mark.asyncio
async def test_search_chefs_by_event_type():
    """Test search_chefs filtering by event type."""
    
    print("\n🔍 Testing search_chefs with event_type filter (wedding)...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {"event_type": "wedding"})
        
        # Check if content exists (might be empty for no match)
        if not result.content or len(result.content) == 0:
            print("⚠ No content returned - event_type might not match any chefs")
            # For wedding, we expect at least some matches, so this is a test failure
            assert False, "Expected at least one chef for wedding event type"
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Should return chefs suitable for weddings
        assert len(chefs) > 0, "Expected at least one chef for weddings"
        assert chefs[0]["match_score"] > 0, "Expected positive match score"
        
        print(f"✓ Found {len(chefs)} chef(s) suitable for weddings")
        print(f"✓ Top match: {chefs[0]['name']} (score: {chefs[0]['match_score']})")


@pytest.mark.asyncio
async def test_search_chefs_combined_filters():
    """Test search_chefs with both specialty and event_type filters."""
    
    print("\n🔍 Testing search_chefs with combined filters (French + wedding)...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {
            "specialty": "French",
            "event_type": "wedding"
        })
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Should return French chefs suitable for weddings
        assert len(chefs) > 0, "Expected at least one French chef"
        
        first_chef = chefs[0]
        assert any("french" in s.lower() for s in first_chef["specialties"]), \
            "Expected French specialty"
        assert first_chef["match_score"] >= 10, "Expected high match score"
        
        print(f"✓ Found {len(chefs)} French chef(s) for weddings")
        print(f"✓ Top match: {first_chef['name']} (score: {first_chef['match_score']})")


@pytest.mark.asyncio
async def test_search_chefs_max_results():
    """Test search_chefs respects max_results parameter."""
    
    print("\n🔍 Testing max_results parameter...")
    
    async with Client(_mcp) as client:
        # Request 3 results
        result = await client.call_tool("search_chefs", {"max_results": 3})
        chefs = json.loads(result.content[0].text)
        assert len(chefs) == 3, f"Expected 3 chefs, got {len(chefs)}"
        
        # Request 1 result
        result = await client.call_tool("search_chefs", {"max_results": 1})
        chefs = json.loads(result.content[0].text)
        assert len(chefs) == 1, f"Expected 1 chef, got {len(chefs)}"
        
        # Request 10 results (we have exactly 10 chefs)
        result = await client.call_tool("search_chefs", {"max_results": 10})
        chefs = json.loads(result.content[0].text)
        assert len(chefs) == 10, f"Expected 10 chefs, got {len(chefs)}"
        
        print("✓ max_results parameter working correctly")


@pytest.mark.asyncio
async def test_search_chefs_no_match():
    """Test search_chefs returns empty list for non-matching specialty."""
    
    print("\n🔍 Testing non-matching specialty filter...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {"specialty": "Martian"})
        
        # For empty results, FastMCP might return empty content or empty list
        if not result.content or len(result.content) == 0:
            # Empty content means no results - this is expected
            print("✓ Correctly returned no content for non-matching specialty")
            return
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Should return empty list
        assert len(chefs) == 0, f"Expected 0 chefs for Martian cuisine, got {len(chefs)}"
        
        print("✓ Correctly returned empty list for non-matching specialty")


@pytest.mark.asyncio
async def test_search_chefs_sorting():
    """Test search_chefs results are sorted by match_score."""
    
    print("\n🔍 Testing result sorting by match_score...")
    
    async with Client(_mcp) as client:
        result = await client.call_tool("search_chefs", {"specialty": "Italian"})
        
        content = result.content[0]
        chefs = json.loads(content.text) if hasattr(content, 'text') else []
        
        # Verify descending match_score order
        scores = [chef["match_score"] for chef in chefs]
        assert scores == sorted(scores, reverse=True), \
            f"Results not sorted by match_score: {scores}"
        
        print(f"✓ Results correctly sorted by match_score: {scores}")


if __name__ == "__main__":
    print("Starting MCP Chef Services Integration Tests")
    print("(Using FastMCP in-memory client)\n")
    print("=" * 60)
    
    try:
        # Run tests
        asyncio.run(test_search_chefs_tool_registration())
        asyncio.run(test_search_chefs_no_filters())
        asyncio.run(test_search_chefs_by_specialty_italian())
        asyncio.run(test_search_chefs_by_specialty_vegan())
        asyncio.run(test_search_chefs_case_insensitive())
        asyncio.run(test_search_chefs_by_event_type())
        asyncio.run(test_search_chefs_combined_filters())
        asyncio.run(test_search_chefs_max_results())
        asyncio.run(test_search_chefs_no_match())
        asyncio.run(test_search_chefs_sorting())
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        raise
