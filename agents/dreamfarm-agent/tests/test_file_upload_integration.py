"""Integration tests for file upload endpoint - real Azure OpenAI Files API.

Run these by selecting `-m integration`. Tests skip at runtime if required
API credentials are not available or code interpreter is not enabled.
"""

import pytest
import os
import io
from fastapi.testclient import TestClient

from src.main import app
from src.services.config_service import ConfigService

pytestmark = pytest.mark.integration


class TestFileUploadIntegration:
    """Integration tests for file upload endpoint that use real Azure OpenAI Files API.
    
    These tests require:
    1. Valid Azure OpenAI API credentials with Files API access
    2. Code Interpreter feature enabled (ENABLE_CODE_INTERPRETER=true)
    3. Authentication disabled or valid JWT token
    
    Run with: pytest -m integration tests/test_file_upload_integration.py
    """
    
    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures."""
        # Check env for integration readiness (skip gracefully if missing)
        has_api_key = any(os.getenv(k) for k in (
            'OPENAI_API_KEY', 'AZURE_OPENAI_API_KEY'
        ))
        if not has_api_key:
            pytest.skip("File upload integration requires OpenAI/Azure API key")
        
        # Ensure Code Interpreter is enabled for integration tests
        os.environ['ENABLE_CODE_INTERPRETER'] = 'true'
        # Disable auth for simpler testing
        os.environ['AUTH_ENABLED'] = 'false'
        # Disable MCP tools to avoid connection issues
        os.environ['FARMER_TOOLS_ENABLED'] = 'false'
        os.environ['TAVILY_ENABLED'] = 'false'
        os.environ['STOCK_TOOL_ENABLED'] = 'false'
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create config and verify code interpreter is enabled
        self.config_service = ConfigService()
        self.config = self.config_service.config
        
        # Skip tests if code interpreter is not properly configured
        if not (hasattr(self.config, 'code_interpreter') and 
                self.config.code_interpreter and 
                self.config.code_interpreter.enabled):
            pytest.skip("Code Interpreter is not enabled in config")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    def test_upload_csv_file(self):
        """Test uploading a CSV file successfully."""
        # Create a sample CSV file in memory
        csv_content = b"date,weight_kg,notes\\n2024-01-01,75.5,Starting weight\\n2024-01-08,75.2,Down a bit"
        
        with TestClient(app) as client:
            files = {"file": ("test_data.csv", io.BytesIO(csv_content), "text/csv")}
            response = client.post("/files/upload", files=files)
        
        # Verify response
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        
        # Check response structure
        assert "file_id" in data
        # Azure OpenAI file IDs use "assistant-" prefix (not "file-")
        assert data["file_id"].startswith("assistant-"), f"Expected file_id to start with 'assistant-', got: {data['file_id']}"
        assert data["filename"] == "test_data.csv"
        assert data["size_bytes"] == len(csv_content)
        assert data["purpose"] == "assistants"
        assert data["status"] == "uploaded"
        
        print(f"\\nSuccessfully uploaded CSV: file_id={data['file_id']}")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    def test_upload_excel_file(self):
        """Test uploading an Excel file."""
        # Create a minimal Excel file (simplified binary content)
        # In reality, this would be a proper Excel file, but for testing we just verify the endpoint accepts .xlsx
        excel_content = b"PK\\x03\\x04" + b"\\x00" * 100  # Minimal ZIP header (Excel is ZIP-based)
        
        with TestClient(app) as client:
            files = {"file": ("data.xlsx", io.BytesIO(excel_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            response = client.post("/files/upload", files=files)
        
        # Should succeed (Azure will handle actual Excel parsing)
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "data.xlsx"
        
        print(f"\\nSuccessfully uploaded Excel: file_id={data['file_id']}")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    def test_upload_invalid_file_type(self):
        """Test that invalid file types are rejected."""
        # Try uploading a .exe file (not allowed)
        exe_content = b"MZ\\x90\\x00"  # PE executable header
        
        with TestClient(app) as client:
            files = {"file": ("malware.exe", io.BytesIO(exe_content), "application/x-msdownload")}
            response = client.post("/files/upload", files=files)
        
        # Should be rejected
        assert response.status_code == 400
        error_data = response.json()
        assert "Unsupported file type" in error_data["detail"]
        
        print("\\nCorrectly rejected .exe file")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    def test_upload_file_too_large(self):
        """Test that files over 30MB are rejected."""
        # Create a file larger than 30MB
        large_content = b"x" * (31 * 1024 * 1024)  # 31MB
        
        with TestClient(app) as client:
            files = {"file": ("huge_file.csv", io.BytesIO(large_content), "text/csv")}
            response = client.post("/files/upload", files=files)
        
        # Should be rejected
        assert response.status_code == 413
        error_data = response.json()
        assert "File too large" in error_data["detail"]
        
        print("\\nCorrectly rejected 31MB file")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    def test_upload_empty_file(self):
        """Test that empty files are rejected."""
        with TestClient(app) as client:
            files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
            response = client.post("/files/upload", files=files)
        
        # Should be rejected
        assert response.status_code == 400
        error_data = response.json()
        assert "File is empty" in error_data["detail"]
        
        print("\\nCorrectly rejected empty file")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    def test_upload_json_file(self):
        """Test uploading a JSON file."""
        json_content = b'{"data": [1, 2, 3, 4, 5], "label": "test"}'
        
        with TestClient(app) as client:
            files = {"file": ("data.json", io.BytesIO(json_content), "application/json")}
            response = client.post("/files/upload", files=files)
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "data.json"
        
        print(f"\\nSuccessfully uploaded JSON: file_id={data['file_id']}")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    def test_upload_txt_file(self):
        """Test uploading a plain text file."""
        txt_content = b"Line 1\\nLine 2\\nLine 3\\nSome data here"
        
        with TestClient(app) as client:
            files = {"file": ("notes.txt", io.BytesIO(txt_content), "text/plain")}
            response = client.post("/files/upload", files=files)
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        assert "file_id" in data
        assert data["filename"] == "notes.txt"
        
        print(f"\\nSuccessfully uploaded text file: file_id={data['file_id']}")
    
    @pytest.mark.skip(reason="Cannot test disabled state with TestClient - app config is loaded at startup")
    def test_upload_when_code_interpreter_disabled(self):
        """Test that upload fails when code interpreter is disabled.
        
        Note: This test is skipped because TestClient captures the app configuration
        at startup. To test the disabled state, you would need to:
        1. Set ENABLE_CODE_INTERPRETER=false in environment
        2. Restart the application
        3. Verify 503 response from /files/upload
        
        The endpoint code correctly checks:
            if not config_service.config.code_interpreter.enabled:
                raise HTTPException(status_code=503, detail="Code interpreter is not enabled")
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration", "-s"])
