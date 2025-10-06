"""Integration tests for VoiceService WebSocket endpoint.

These tests verify the voice WebSocket endpoint works correctly with FastAPI's
TestClient, including JWT authentication, connection handling, and basic data flow.
"""
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_voice_service():
    """Mock VoiceService for testing WebSocket endpoint."""
    mock = MagicMock()
    mock.handle_voice_session = AsyncMock()
    return mock


@pytest.fixture
def mock_auth_service():
    """Mock auth_service for testing JWT validation."""
    mock = MagicMock()
    mock.validate.return_value = {
        "sub": "test-user-id",
        "preferred_username": "testuser",
        "realm_access": {"roles": []}
    }
    mock.extract_identity.return_value = ("testuser", False)
    return mock


@pytest.fixture
def voice_test_client(mock_voice_service, mock_auth_service):
    """Provide a TestClient with voice/auth/template services swapped for mocks."""
    from src import main
    from src.main import app

    template_mock = MagicMock()
    template_mock.render_template.return_value = "voice-system-prompt"

    config_placeholder = SimpleNamespace(config=SimpleNamespace())

    original_auth = main.auth_service
    original_voice = main.voice_service
    original_template = main.template_service
    original_config = main.config_service

    with TestClient(app) as client:
        main.auth_service = mock_auth_service
        main.voice_service = mock_voice_service
        main.template_service = template_mock
        main.config_service = config_placeholder
        yield client

    main.auth_service = original_auth
    main.voice_service = original_voice
    main.template_service = original_template
    main.config_service = original_config


def test_voice_websocket_requires_auth(voice_test_client):
    """Test that voice WebSocket requires JWT token."""
    with voice_test_client.websocket_connect("/voice/test-thread-123") as websocket:
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_text()


def test_voice_websocket_invalid_jwt(voice_test_client, mock_auth_service):
    """Test that voice WebSocket rejects invalid JWT."""
    # Mock auth_service to raise exception
    mock_auth_service.validate.side_effect = Exception("Invalid token")

    with voice_test_client.websocket_connect("/voice/test-thread-123?token=invalid-token") as websocket:
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_text()


def test_voice_websocket_connection_with_valid_token(
    voice_test_client,
    mock_auth_service,
    mock_voice_service
):
    """Test successful WebSocket connection with valid JWT."""
    # Mock handle_voice_session to immediately return
    async def mock_handler(websocket, thread_id, user):
        await websocket.close()
    
    mock_voice_service.handle_voice_session = mock_handler

    # Connect with token (mock_auth_service makes it valid)
    with voice_test_client.websocket_connect("/voice/test-thread-123?token=valid-token"):
        pass


def test_voice_websocket_receives_messages(
    voice_test_client,
    mock_auth_service,
    mock_voice_service
):
    """Test that WebSocket can receive and send messages."""
    # Mock handle_voice_session to echo messages
    async def mock_handler(*, websocket, thread_id, user_id, system_prompt, enable_heavy_tools):
        try:
            data = await websocket.receive_json()
            # Echo back
            await websocket.send_json({"type": "echo", "data": data})
        except Exception:
            pass
    
    mock_voice_service.handle_voice_session = mock_handler

    with voice_test_client.websocket_connect("/voice/test-thread-123?token=valid-token") as websocket:
        # Send test message
        test_message = {"type": "test", "content": "hello"}
        websocket.send_json(test_message)

        # Receive echo
        response = websocket.receive_json()
        assert response["type"] == "echo"
        assert response["data"] == test_message


def test_voice_websocket_thread_id_passed_to_service(
    voice_test_client,
    mock_auth_service,
    mock_voice_service
):
    """Test that thread_id from URL is passed to VoiceService."""
    call_args = []
    
    async def mock_handler(*, websocket, thread_id, user_id, system_prompt, enable_heavy_tools):
        call_args.append({"thread_id": thread_id, "user_id": user_id, "heavy": enable_heavy_tools})
        await websocket.close()
    
    mock_voice_service.handle_voice_session = mock_handler

    with voice_test_client.websocket_connect("/voice/my-thread-456?token=valid-token"):
        pass
    
    # Verify thread_id was passed correctly
    assert len(call_args) == 1
    assert call_args[0]["thread_id"] == "my-thread-456"
    assert call_args[0]["user_id"] == "testuser"
    assert call_args[0]["heavy"] is False


def test_voice_websocket_error_handling(
    voice_test_client,
    mock_auth_service,
    mock_voice_service
):
    """Test that WebSocket handles errors gracefully."""
    # Mock handle_voice_session to raise an error
    async def mock_handler(websocket, thread_id, user):
        raise Exception("Simulated error")
    
    mock_voice_service.handle_voice_session = mock_handler
    
    # Connection should close on error
    with voice_test_client.websocket_connect("/voice/test-thread?token=valid-token"):
        pass


def test_voice_websocket_multiple_connections(
    voice_test_client,
    mock_auth_service,
    mock_voice_service
):
    """Test that multiple WebSocket connections can be handled."""
    connection_count = []
    
    async def mock_handler(*, websocket, thread_id, user_id, system_prompt, enable_heavy_tools):
        connection_count.append(thread_id)
        await websocket.close()
    
    mock_voice_service.handle_voice_session = mock_handler

    # Connect to different threads
    with voice_test_client.websocket_connect("/voice/thread-1?token=valid-token"):
        pass

    with voice_test_client.websocket_connect("/voice/thread-2?token=valid-token"):
        pass
    
    assert len(connection_count) == 2
    assert "thread-1" in connection_count
    assert "thread-2" in connection_count
