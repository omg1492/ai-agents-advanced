"""Integration tests for VoiceService WebSocket endpoint.

These tests verify the voice WebSocket endpoint works correctly with FastAPI's
TestClient, including JWT authentication, connection handling, and basic data flow.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_voice_service():
    """Mock VoiceService for testing WebSocket endpoint."""
    with patch('src.main.voice_service') as mock:
        mock.handle_voice_session = AsyncMock()
        yield mock


@pytest.fixture
def mock_auth_service():
    """Mock auth_service for testing JWT validation."""
    with patch('src.main.auth_service') as mock:
        # Mock validate method to return claims
        mock.validate.return_value = {
            "sub": "test-user-id",
            "preferred_username": "testuser",
            "realm_access": {"roles": []}
        }
        # Mock extract_identity to return username and is_vip
        mock.extract_identity.return_value = ("testuser", False)
        yield mock


def test_voice_websocket_requires_auth():
    """Test that voice WebSocket requires JWT token."""
    from src.main import app
    with patch('src.main.voice_service'):
        client = TestClient(app)
        # Try to connect without token - should get 4001 error
        with client.websocket_connect("/voice/test-thread-123") as _websocket:
            # Should close with error
            assert False, "Should have closed with error"


def test_voice_websocket_invalid_jwt(mock_auth_service):
    """Test that voice WebSocket rejects invalid JWT."""
    from src.main import app
    # Mock auth_service to raise exception
    mock_auth_service.validate.side_effect = Exception("Invalid token")
    
    with patch('src.main.voice_service'):
        client = TestClient(app)
        with client.websocket_connect("/voice/test-thread-123?token=invalid-token") as _websocket:
            # Should close with error
            assert False, "Should have closed with error"


def test_voice_websocket_connection_with_valid_token(
    mock_auth_service,
    mock_voice_service
):
    """Test successful WebSocket connection with valid JWT."""
    from src.main import app
    # Mock handle_voice_session to immediately return
    async def mock_handler(websocket, thread_id, user):
        await websocket.close()
    
    mock_voice_service.handle_voice_session = mock_handler
    
    client = TestClient(app)
    # Connect with token (mock_auth_service makes it valid)
    with client.websocket_connect("/voice/test-thread-123?token=valid-token") as _websocket:
        # Connection should succeed
        pass


def test_voice_websocket_receives_messages(
    mock_auth_service,
    mock_voice_service
):
    """Test that WebSocket can receive and send messages."""
    from src.main import app
    # Mock handle_voice_session to echo messages
    async def mock_handler(websocket, thread_id, user):
        try:
            data = await websocket.receive_json()
            # Echo back
            await websocket.send_json({"type": "echo", "data": data})
        except Exception:
            pass
    
    mock_voice_service.handle_voice_service = mock_handler
    
    client = TestClient(app)
    with client.websocket_connect("/voice/test-thread-123?token=valid-token") as websocket:
        # Send test message
        test_message = {"type": "test", "content": "hello"}
        websocket.send_json(test_message)
        
        # Receive echo
        response = websocket.receive_json()
        assert response["type"] == "echo"
        assert response["data"] == test_message


def test_voice_websocket_thread_id_passed_to_service(
    mock_auth_service,
    mock_voice_service
):
    """Test that thread_id from URL is passed to VoiceService."""
    from src.main import app
    call_args = []
    
    async def mock_handler(websocket, thread_id, user):
        call_args.append({"thread_id": thread_id, "user": user})
        await websocket.close()
    
    mock_voice_service.handle_voice_session = mock_handler
    
    client = TestClient(app)
    with client.websocket_connect("/voice/my-thread-456?token=valid-token"):
        pass
    
    # Verify thread_id was passed correctly
    assert len(call_args) == 1
    assert call_args[0]["thread_id"] == "my-thread-456"
    assert call_args[0]["user"]["username"] == "testuser"


def test_voice_websocket_error_handling(
    mock_auth_service,
    mock_voice_service
):
    """Test that WebSocket handles errors gracefully."""
    from src.main import app
    # Mock handle_voice_session to raise an error
    async def mock_handler(websocket, thread_id, user):
        raise Exception("Simulated error")
    
    mock_voice_service.handle_voice_session = mock_handler
    
    client = TestClient(app)
    # Connection should close on error
    with client.websocket_connect("/voice/test-thread?token=valid-token") as _websocket:
        # Service will handle error and close
        pass


def test_voice_websocket_multiple_connections(
    mock_auth_service,
    mock_voice_service
):
    """Test that multiple WebSocket connections can be handled."""
    from src.main import app
    connection_count = []
    
    async def mock_handler(websocket, thread_id, user):
        connection_count.append(thread_id)
        await websocket.close()
    
    mock_voice_service.handle_voice_session = mock_handler
    
    client = TestClient(app)
    # Connect to different threads
    with client.websocket_connect("/voice/thread-1?token=valid-token"):
        pass
    
    with client.websocket_connect("/voice/thread-2?token=valid-token"):
        pass
    
    assert len(connection_count) == 2
    assert "thread-1" in connection_count
    assert "thread-2" in connection_count
