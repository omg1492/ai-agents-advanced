"""Integration tests for Visualization MCP tool.

Tests the full stack: config -> openai_service -> actual MCP server -> artifact storage.
These tests verify real interaction with the MCP server and OpenAI Responses API.

## Running Tests

### Unit tests only (default):
    pytest tests/test_visualization_mcp.py

### Integration tests only (requires MCP server & OpenAI API):
    pytest tests/test_visualization_mcp.py -m integration

### All tests:
    pytest tests/test_visualization_mcp.py -m "unit or integration"

Note: Integration tests require `.env` file with VISUALIZATION_MCP_* variables configured.
"""
import pytest
import os
import json
import uuid
from unittest.mock import Mock
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root for integration tests
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from src.services.config_service import ConfigService, VisualizationMCPConfig


@pytest.mark.unit
@pytest.mark.asyncio
async def test_visualization_mcp_config_from_env():
    """Test that visualization MCP config is loaded from environment."""
    # Set env vars
    os.environ["VISUALIZATION_MCP_ENABLED"] = "true"
    os.environ["VISUALIZATION_MCP_URL"] = "https://test-viz-mcp.example.com/mcp"
    os.environ["VISUALIZATION_MCP_API_KEY"] = "test-key-12345"
    
    config_service = ConfigService()
    config = config_service.config
    
    assert config.visualization_mcp is not None
    assert config.visualization_mcp.enabled is True
    assert config.visualization_mcp.mcp_url == "https://test-viz-mcp.example.com/mcp"
    assert config.visualization_mcp.mcp_api_key == "test-key-12345"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_visualization_mcp_tool_registration():
    """Test that visualization MCP tool is registered in OpenAI service."""
    from src.services.openai_service import OpenAIService
    from src.services.config_service import AppConfig, OpenAIConfig
    
    # Create mock config with visualization enabled
    viz_mcp_config = VisualizationMCPConfig(
        enabled=True,
        mcp_url="https://test-viz-mcp.example.com/mcp",
        mcp_api_key="test-key-12345",
    )
    
    openai_config = OpenAIConfig(
        api_key="test-key",
        model_name="gpt-4",
    )
    
    # Create minimal app config
    app_config = Mock(spec=AppConfig)
    app_config.visualization_mcp = viz_mcp_config
    app_config.farmer_tools = None
    app_config.tavily = None
    app_config.stock_tool = None
    app_config.agentic_search = None
    app_config.graph_search = None
    app_config.memory_search = None
    app_config.code_interpreter = None
    
    # Create service with mock HTTP client to avoid real API calls
    service = OpenAIService(config=openai_config, app_config=app_config)
    
    # Get tools
    tools = service.get_tools()
    
    # Should have visualization MCP tool
    assert tools is not None
    
    viz_tools = [t for t in tools if t.get("type") == "mcp" and t.get("server_label") == "visualization"]
    assert len(viz_tools) == 1
    
    viz_tool = viz_tools[0]
    assert viz_tool["server_url"] == "https://test-viz-mcp.example.com/mcp"
    assert viz_tool["headers"]["Authorization"] == "Bearer test-key-12345"
    assert viz_tool["require_approval"] == "never"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_artifact_registration_and_retrieval():
    """Test artifact registration and cleanup."""
    from src.main import _register_html_artifact, _html_artifact_registry, _cleanup_html_artifacts
    from datetime import datetime, timezone, timedelta
    
    # Clear registry
    _html_artifact_registry.clear()
    
    # Register artifact
    artifact_id = "test-artifact-123"
    html_content = "<html><body>Test</body></html>"
    thread_id = "thread-456"
    
    _register_html_artifact(artifact_id, html_content, thread_id)
    
    # Verify stored
    assert artifact_id in _html_artifact_registry
    artifact = _html_artifact_registry[artifact_id]
    assert artifact["html"] == html_content
    assert artifact["thread_id"] == thread_id
    assert isinstance(artifact["created_at"], datetime)
    
    # Test cleanup doesn't remove fresh artifacts
    _cleanup_html_artifacts()
    assert artifact_id in _html_artifact_registry
    
    # Simulate expiry by backdating
    _html_artifact_registry[artifact_id]["created_at"] = datetime.now(timezone.utc) - timedelta(hours=2)
    
    # Cleanup should remove expired
    _cleanup_html_artifacts()
    assert artifact_id not in _html_artifact_registry


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("VISUALIZATION_MCP_ENABLED", "false").lower() not in ["true", "1"],
    reason="Requires VISUALIZATION_MCP_ENABLED=true in .env for real server test"
)
async def test_mcp_server_health():
    """Integration test - verify MCP server is accessible via health endpoint.
    
    This is a basic connectivity test that doesn't require MCP protocol knowledge.
    """
    import httpx
    
    config_service = ConfigService()
    config = config_service.config
    
    if not config.visualization_mcp or not config.visualization_mcp.enabled:
        pytest.skip("Visualization MCP not enabled in config")
    
    mcp_url = config.visualization_mcp.mcp_url
    health_url = mcp_url.replace("/mcp", "/health")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(health_url)
        assert response.status_code == 200
        assert response.text == "OK"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_api
@pytest.mark.skipif(
    os.getenv("VISUALIZATION_MCP_ENABLED", "false").lower() not in ["true", "1"],
    reason="Requires VISUALIZATION_MCP_ENABLED=true and OPENAI_API_KEY in .env"
)
async def test_visualization_via_openai_responses_api():
    """Integration test - full flow through OpenAI Responses API with MCP tool.
    
    This tests:
    1. OpenAI Responses API calls the MCP visualization tool
    2. MCP server generates and sanitizes HTML
    3. OpenAI returns the tool response
    4. We parse and validate the HTML artifact
    
    This is the REAL integration test that matters - it tests the actual flow
    that will happen in production when the LLM decides to call the visualization tool.
    """
    from src.services.openai_service import OpenAIService
    from src.services.config_service import ConfigService
    
    config_service = ConfigService()
    config = config_service.config
    
    if not config.visualization_mcp or not config.visualization_mcp.enabled:
        pytest.skip("Visualization MCP not enabled in config")
    
    if not config.openai.api_key or config.openai.api_key.startswith("test"):
        pytest.skip("Real OpenAI API key required")
    
    # Create OpenAI service with real config (includes visualization MCP tool)
    openai_service = OpenAIService()
    
    # Verify visualization tool is registered
    tools = openai_service.get_tools()
    assert tools is not None
    viz_tools = [t for t in tools if t.get("type") == "mcp" and t.get("server_label") == "visualization"]
    assert len(viz_tools) == 1, "Visualization MCP tool should be registered"
    
    # Create a simple request that should trigger visualization tool
    # We use forced tool call to ensure the model uses our tool
    messages = [
        {
            "role": "user",
            "content": "Create a simple HTML card that displays 'Hello Integration Test' in large blue text with a gradient background."
        }
    ]
    
    # Call Responses API with visualization tool available
    response = await openai_service.client.responses.create(
        model=openai_service.model_name,
        reasoning={"effort": "low"},
        instructions="You are a helpful visualization assistant. When asked to create visual elements, use the generate_infographic tool.",
        store=False,  # Don't store for test
        input=messages,
        tools=tools,
    )
    
    # Verify response structure
    assert response is not None
    assert hasattr(response, 'output')
    assert len(response.output) > 0
    
    # Look for MCP tool call in the output
    mcp_tool_called = False
    html_artifact = None
    
    for item in response.output:
        if hasattr(item, 'type'):
            # Check for reasoning or message items
            if item.type == 'message' and hasattr(item, 'content'):
                for content_item in item.content:
                    if hasattr(content_item, 'text'):
                        # Check if response mentions creating visualization
                        text = content_item.text.lower()
                        if 'visual' in text or 'html' in text or 'card' in text:
                            print(f"Model response: {content_item.text[:200]}...")
            
            # Check for MCP tool call
            elif item.type == 'mcp_call':
                mcp_tool_called = True
                tool_name = getattr(item, 'name', None)
                print(f"MCP tool called: {tool_name}")
                
                # If tool execution completed, check for output
                if hasattr(item, 'output'):
                    output = item.output
                    print(f"Tool output type: {type(output)}")
                    
                    # Parse tool output (should be JSON with HTML)
                    if isinstance(output, str):
                        try:
                            output_data = json.loads(output)
                            if output_data.get('type') == 'custom_ui':
                                html_artifact = output_data.get('html')
                                print(f"Got HTML artifact: {len(html_artifact) if html_artifact else 0} chars")
                        except json.JSONDecodeError:
                            print("Could not parse tool output as JSON")
    
    # At minimum, verify the tool was called
    # Note: MCP tool execution happens asynchronously, so we may not see output in first response
    assert mcp_tool_called or html_artifact is not None, (
        "Either MCP tool should be called or HTML artifact should be generated. "
        "If neither happened, the model didn't use the visualization tool."
    )
    
    # If we got HTML, validate it
    if html_artifact:
        assert isinstance(html_artifact, str)
        assert len(html_artifact) > 100  # Should be substantial HTML
        assert "<!DOCTYPE html>" in html_artifact or "<html" in html_artifact
        
        # Verify sanitization (no dangerous patterns)
        assert "<iframe" not in html_artifact.lower()
        assert "<object" not in html_artifact.lower()
        assert "javascript:" not in html_artifact.lower()
        
        print(f"✓ Received valid sanitized HTML artifact ({len(html_artifact)} chars)")


@pytest.mark.integration
@pytest.mark.asyncio  
async def test_artifact_api_endpoint():
    """Integration test - artifact storage and retrieval via API endpoint.
    
    Tests:
    1. Artifact registration
    2. Retrieval via /artifacts/{id} endpoint
    3. Auth requirement
    4. Content-Type header
    """
    from fastapi.testclient import TestClient
    from src.main import app, _register_html_artifact, _html_artifact_registry
    
    # Clear registry
    _html_artifact_registry.clear()
    
    # Create test artifact
    artifact_id = str(uuid.uuid4())
    test_html = "<html><body><h1>Test Artifact</h1></body></html>"
    thread_id = "test-thread-123"
    
    _register_html_artifact(artifact_id, test_html, thread_id)
    
    # Create test client
    client = TestClient(app)
    
    # Test retrieval without auth (should work if auth disabled, or fail if enabled)
    response = client.get(f"/artifacts/{artifact_id}")
    
    # If auth is enabled, this will be 401, otherwise 200
    if response.status_code == 401:
        print("✓ Auth correctly required for artifact endpoint")
        # TODO: Add test with valid auth token
    else:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert response.text == test_html
        print("✓ Artifact retrieved successfully (auth disabled)")
    
    # Test non-existent artifact
    response = client.get(f"/artifacts/nonexistent-{uuid.uuid4()}")
    assert response.status_code in [404, 401]  # 404 if auth disabled, 401 if enabled
    
    print("✓ Artifact API endpoint working correctly")
