"""
Integration test using FastMCP in-memory client.

This test connects directly to the MCP server instance (no network/process overhead)
and makes a real LLM call to generate visualization HTML.
"""

import asyncio
import json
import sys
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables before importing main
load_dotenv()

# Import after path setup and env loading
from fastmcp import Client
from main import _mcp as mcp


@pytest.mark.asyncio
async def test_generate_visualization():
    """Test the generate_html tool via FastMCP in-memory client."""
    
    print("Connecting to MCP server (in-memory)...")
    
    # Use in-memory transport by passing server instance directly
    async with Client(mcp) as client:
        print("✓ Connected to MCP server")
        
        # List available tools
        tools = await client.list_tools()
        print(f"✓ Available tools: {[tool.name for tool in tools]}")
        
        # Test: Generate infographic
        print("\n🔍 Testing infographic generation...")
        result = await client.call_tool(
            "generate_infographic",
            {
                "description": "Create a welcome card with the title 'Hello FastMCP' and a friendly greeting message",
                "style": "card"
            }
        )
        
        print("✓ Tool call completed")
        
        # Check the result
        assert result is not None
        assert result.content is not None
        assert len(result.content) > 0
        
        # Extract HTML from result
        import json
        content = result.content[0]
        result_data = json.loads(content.text) if hasattr(content, 'text') else {}
        
        assert result_data.get("type") == "custom_ui", f"Wrong type: {result_data.get('type')}"
        html = result_data.get("html", "")
        assert html.strip().startswith("<!DOCTYPE html>"), "Invalid HTML"
        assert "FastMCP" in html or "fastmcp" in html.lower(), "Missing title content"
        
        metadata = result_data.get("metadata", {})
        print(f"\n✓ Generated HTML: {len(html)} characters")
        print(f"✓ Generator: {metadata.get('generator')}")
        print(f"✓ Model: {metadata.get('model')}")
        print(f"\nHTML preview (first 200 chars):\n{html[:200]}...")
        
        return html


@pytest.mark.asyncio
async def test_with_data():
    """Test generation with structured data."""
    
    print("\n🔍 Testing generation with structured data...")
    
    async with Client(mcp) as client:
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
        
        import json
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


if __name__ == "__main__":
    print("Starting MCP Visualization Generator Integration Tests")
    print("(Using FastMCP in-memory client)\n")
    print("=" * 60)
    
    try:
        # Run tests
        asyncio.run(test_generate_visualization())
        asyncio.run(test_with_data())
        
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
