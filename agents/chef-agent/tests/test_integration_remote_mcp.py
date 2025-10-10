"""Integration tests for Chef Agent with remote MCP server.

These tests run against the deployed Chef Services MCP server on Azure
to verify end-to-end functionality including:
- OpenAI Responses API integration
- MCP tool discovery and execution
- Complete query workflows with real tool calls

Prerequisites:
- OPENAI_API_KEY must be set in .env
- CHEF_SERVICES_MCP_URL must point to deployed Azure instance
- CHEF_SERVICES_MCP_API_KEY must match server configuration
"""

import pytest
import os
from dotenv import load_dotenv

from src.services.config_service import ConfigService
from src.services.openai_service import OpenAIService


# Load environment for integration tests
load_dotenv()


@pytest.fixture
def config_service():
    """Fixture providing real ConfigService for integration tests."""
    return ConfigService()


@pytest.fixture
def openai_service(config_service):
    """Fixture providing real OpenAIService with remote MCP connection."""
    return OpenAIService(
        config=config_service.get_openai_config(),
        app_config=config_service.config,
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestRemoteMCPIntegration:
    """Integration tests against live Chef Services MCP server."""

    async def test_mcp_connection_and_tool_discovery(self, openai_service):
        """Test that service can connect to MCP server and register tools."""
        # Get tools - should include MCP registration
        tools = openai_service.get_tools()
        
        assert len(tools) == 1
        assert tools[0]["type"] == "mcp"
        
        # Verify Azure OpenAI MCP format (server_url, server_label, etc.)
        assert "server_label" in tools[0]
        assert tools[0]["server_label"] == "chef_services"
        assert "server_url" in tools[0]
        assert "require_approval" in tools[0]
        assert "headers" in tools[0]
        assert "Authorization" in tools[0]["headers"]
        
        # Verify MCP URL is set correctly
        mcp_url = tools[0]["server_url"]
        assert mcp_url.startswith("http"), "MCP URL should be HTTP(S)"
        assert "mcp" in mcp_url.lower(), "URL should contain 'mcp'"

    async def test_chef_search_query(self, openai_service):
        """Test complete workflow: user query -> MCP tool call -> response.
        
        This test verifies that:
        1. OpenAI Responses API accepts the query
        2. Model decides to use search_chefs MCP tool
        3. MCP server executes the tool successfully
        4. Response includes relevant chef information
        """
        query = "Find me an Italian chef who specializes in pasta and has experience with private dining"
        
        response_text, response_id = await openai_service.generate_response(
            user_text=query,
            system_prompt="You are a culinary services assistant. Use available tools to help users find chefs and services.",
            previous_response_id=None,
        )
        
        # Verify we got a response
        assert response_text, "Response should not be empty"
        assert response_id, "Response ID should be returned"
        assert len(response_text) > 50, "Response should be substantive"
        
        # Response should mention chefs or specific chef names
        response_lower = response_text.lower()
        assert any(keyword in response_lower for keyword in ["chef", "italian", "pasta", "cooking"]), \
            "Response should be relevant to chef search"

    async def test_service_search_query(self, openai_service):
        """Test service search with catering query."""
        query = "I need catering service for 40 people, preferably Italian cuisine"
        
        response_text, response_id = await openai_service.generate_response(
            user_text=query,
            system_prompt="You are a culinary services assistant. Use available tools to search for services.",
        )
        
        assert response_text
        assert response_id
        
        # Should mention catering or services
        response_lower = response_text.lower()
        assert any(keyword in response_lower for keyword in ["catering", "service", "guest", "people"]), \
            "Response should address catering query"

    async def test_availability_check_query(self, openai_service):
        """Test availability checking workflow."""
        # First find a chef, then check availability
        query = "Is there a French chef available on December 25th, 2025?"
        
        response_text, response_id = await openai_service.generate_response(
            user_text=query,
            system_prompt="You are a culinary services assistant. Check chef availability using the tools.",
        )
        
        assert response_text
        assert response_id
        
        # Response should discuss availability
        response_lower = response_text.lower()
        assert any(keyword in response_lower for keyword in ["available", "availability", "date", "december"]), \
            "Response should address availability"

    async def test_pricing_calculation_query(self, openai_service):
        """Test pricing calculation workflow."""
        query = "How much would it cost to hire a chef for 25 guests with a complex menu?"
        
        response_text, response_id = await openai_service.generate_response(
            user_text=query,
            system_prompt="You are a culinary services assistant. Calculate pricing using available tools.",
        )
        
        assert response_text
        assert response_id
        
        # Response should include pricing information
        response_lower = response_text.lower()
        assert any(keyword in response_lower for keyword in ["price", "cost", "$", "quote", "total"]), \
            "Response should include pricing details"

    async def test_multi_turn_conversation(self, openai_service):
        """Test stateful conversation with previous_response_id."""
        # First query
        query1 = "Find me Italian chefs"
        response1_text, response1_id = await openai_service.generate_response(
            user_text=query1,
            system_prompt="You are a culinary services assistant.",
        )
        
        assert response1_text
        assert response1_id
        
        # Follow-up query using previous response ID
        query2 = "What about their availability next week?"
        response2_text, response2_id = await openai_service.generate_response(
            user_text=query2,
            system_prompt="You are a culinary services assistant.",
            previous_response_id=response1_id,
        )
        
        assert response2_text
        assert response2_id
        assert response2_id != response1_id, "Second response should have different ID"
        
        # Second response should reference context from first query
        # (this is best-effort as it depends on model behavior)
        response2_lower = response2_text.lower()
        assert "availability" in response2_lower or "available" in response2_lower

    async def test_complex_booking_workflow(self, openai_service):
        """Test complex multi-step booking workflow."""
        query = """I'm planning a wedding reception for 80 guests on July 15th, 2026.
        I need:
        - An Italian chef who can handle large events
        - Mediterranean menu with wine pairing
        - Check availability and give me a detailed price quote
        """
        
        response_text, response_id = await openai_service.generate_response(
            user_text=query,
            system_prompt="You are a culinary services assistant. Use multiple tools as needed to fulfill requests.",
        )
        
        assert response_text
        assert response_id
        assert len(response_text) > 200, "Complex query should yield detailed response"
        
        # Response should address multiple aspects
        response_lower = response_text.lower()
        
        # Should mention chefs or search
        assert any(keyword in response_lower for keyword in ["chef", "italian", "mediterranean"])
        
        # Should address availability or pricing
        assert any(keyword in response_lower for keyword in [
            "available", "availability", "price", "cost", "quote", "$"
        ])

    async def test_error_handling_invalid_date(self, openai_service):
        """Test that invalid dates are handled gracefully."""
        query = "Check if any chef is available on February 30th, 2025"
        
        response_text, response_id = await openai_service.generate_response(
            user_text=query,
            system_prompt="You are a culinary services assistant.",
        )
        
        assert response_text
        assert response_id
        
        # Should acknowledge the issue with the date
        response_lower = response_text.lower()
        # Model should either refuse or suggest valid date
        assert any(keyword in response_lower for keyword in [
            "invalid", "not valid", "doesn't exist", "cannot", "error", "correct date"
        ])


# Skip integration tests by default (run with: pytest -m integration)
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 and valid credentials"
)
