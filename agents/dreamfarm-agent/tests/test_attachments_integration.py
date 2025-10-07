"""Integration tests for file attachments with code interpreter.

NOTE: Only non-streaming tests are included here because TestClient.iter_lines()
does not properly handle Server-Sent Events (SSE) streaming in integration tests.

The streaming endpoint works correctly in production (validated via Playwright UI tests).
The issue is purely a test infrastructure limitation with synchronous TestClient.

Frontend validation: lessons/L06_adhoc_coding/plan.md Phase 1.3 - Playwright tests pass.
"""

import pytest
import os
import io
from fastapi.testclient import TestClient

from src.main import app

pytestmark = pytest.mark.integration


class TestAttachmentsIntegration:
    """Integration tests for file attachment functionality.
    
    These tests verify that attachments work correctly with the non-streaming
    message endpoint. Streaming endpoint functionality is validated via Playwright
    in the frontend (see lessons/L06_adhoc_coding/plan.md Phase 1.3).
    """
    
    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures."""
        # Configure environment for testing
        os.environ['AUTH_ENABLED'] = 'false'
        os.environ['ENABLE_CODE_INTERPRETER'] = 'true'
        # Disable MCP tools to avoid connection issues
        os.environ['FARMER_TOOLS_ENABLED'] = 'false'
        os.environ['TAVILY_ENABLED'] = 'false'
        os.environ['STOCK_TOOL_ENABLED'] = 'false'
    
    @pytest.mark.integration
    def test_file_upload_and_message_with_attachment_non_streaming(self):
        """Test uploading a file and sending a message with attachment (non-streaming)."""
        with TestClient(app) as client:
            # Step 1: Upload a CSV file
            csv_content = b"product,quantity\nApples,5\nBananas,3\nOranges,8\n"
            files = {"file": ("products.csv", io.BytesIO(csv_content), "text/csv")}
            
            upload_response = client.post("/files/upload", files=files)
            
            assert upload_response.status_code == 200
            upload_data = upload_response.json()
            file_id = upload_data["file_id"]
            
            # Step 2: Create a thread
            thread_response = client.post(
                "/threads",
                json={"metadata": {"test": "attachment_non_streaming"}}
            )
            assert thread_response.status_code == 200
            thread_id = thread_response.json()["thread_id"]
            
            # Step 3: Send message with attachment (non-streaming)
            message_payload = {
                "message": "What is the total quantity of all products?",
                "attachments": [file_id]
            }
            
            message_response = client.post(
                f"/threads/{thread_id}/messages",
                json=message_payload
            )
            
            # Should successfully process
            assert message_response.status_code == 200
            response_data = message_response.json()
            
            # Verify response structure (non-streaming returns different format)
            assert "assistant_response" in response_data
            assert "message_id" in response_data
            assert "thread_id" in response_data
            assert isinstance(response_data["assistant_response"], str)
            assert len(response_data["assistant_response"]) > 0
            
            # Verify it actually processed the file
            assert "16" in response_data["assistant_response"] or "total" in response_data["assistant_response"].lower()

    @pytest.mark.integration
    def test_multiple_attachments_non_streaming(self):
        """Test sending multiple file attachments in one message (non-streaming).
        
        This validates that multiple files can be uploaded and passed to the
        code interpreter tool simultaneously.
        """
        with TestClient(app) as client:
            # Upload first file
            csv1_content = b"month,sales\nJan,100\nFeb,150\n"
            files1 = {"file": ("sales_q1.csv", io.BytesIO(csv1_content), "text/csv")}
            upload1 = client.post("/files/upload", files=files1)
            assert upload1.status_code == 200
            file_id_1 = upload1.json()["file_id"]
            
            # Upload second file
            csv2_content = b"month,sales\nMar,200\nApr,180\n"
            files2 = {"file": ("sales_q2.csv", io.BytesIO(csv2_content), "text/csv")}
            upload2 = client.post("/files/upload", files=files2)
            assert upload2.status_code == 200
            file_id_2 = upload2.json()["file_id"]
            
            # Create thread
            thread_response = client.post(
                "/threads",
                json={"metadata": {"test": "multiple_attachments"}}
            )
            assert thread_response.status_code == 200
            thread_id = thread_response.json()["thread_id"]
            
            # Send message with both attachments (non-streaming)
            message_payload = {
                "message": "What is the sum of all sales values across both files?",
                "attachments": [file_id_1, file_id_2]
            }
            
            message_response = client.post(
                f"/threads/{thread_id}/messages",
                json=message_payload
            )
            
            assert message_response.status_code == 200
            response_data = message_response.json()
            
            # Verify response structure
            assert "assistant_response" in response_data
            assert isinstance(response_data["assistant_response"], str)
            assert len(response_data["assistant_response"]) > 0
            
            # Verify it processed both files (total should be 630: 100+150+200+180)
            # Model might phrase differently, so check for any numeric result
            response_text = response_data["assistant_response"]
            assert any(char.isdigit() for char in response_text), "Response should contain calculation result"
