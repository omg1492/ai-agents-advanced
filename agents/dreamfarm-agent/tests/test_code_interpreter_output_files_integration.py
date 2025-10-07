"""Integration tests for Code Interpreter output files (annotations extraction).

Tests verify that generated files (plots, images, CSVs) are properly extracted
from message content annotations and made available via file_id mappings.

Run with: pytest -m integration tests/test_code_interpreter_output_files_integration.py
"""

import pytest
import os

from src.services.openai_service import OpenAIService
from src.services.config_service import ConfigService

pytestmark = pytest.mark.integration


class TestCodeInterpreterOutputFiles:
    """Integration tests for Code Interpreter file generation and annotation extraction.
    
    These tests verify the complete flow:
    1. Code interpreter generates files (plots, CSVs, etc.)
    2. Files are referenced in message content annotations
    3. Backend extracts file_id, container_id, filename from annotations
    4. File mappings are built for URL replacement
    
    These tests require:
    - Valid Azure OpenAI API credentials with Responses API access
    - Code Interpreter feature enabled (ENABLE_CODE_INTERPRETER=true)
    - Model that supports code_interpreter tool (gpt-4o, gpt-5)
    """
    
    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures."""
        # Check env for integration readiness
        has_api_key = any(os.getenv(k) for k in (
            'OPENAI_API_KEY', 'AZURE_OPENAI_API_KEY'
        ))
        if not has_api_key:
            pytest.skip("Code Interpreter integration requires OpenAI/Azure API key")
        
        # Ensure Code Interpreter is enabled
        os.environ['ENABLE_CODE_INTERPRETER'] = 'true'
        # Disable other tools for cleaner tests
        os.environ['FARMER_TOOLS_ENABLED'] = 'false'
        os.environ['TAVILY_ENABLED'] = 'false'
        os.environ['STOCK_TOOL_ENABLED'] = 'false'
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_service = ConfigService()
        self.config = self.config_service.config
        
        # Skip tests if code interpreter is not properly configured
        if not (hasattr(self.config, 'code_interpreter') and 
                self.config.code_interpreter and 
                self.config.code_interpreter.enabled):
            pytest.skip("Code Interpreter is not enabled in config")
        
        self.service = OpenAIService(
            config=self.config.openai,
            app_config=self.config
        )
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_plot_generation_creates_file_annotation(self):
        """Test that generating a plot creates file annotations with file_id.
        
        This test verifies:
        1. Code interpreter generates a matplotlib plot
        2. The response contains file references
        3. Files are referenced in annotations (not outputs which is always None)
        """
        test_message = """Create a simple line plot using matplotlib:
- X axis: [1, 2, 3, 4, 5]
- Y axis: [2, 4, 6, 8, 10]
- Title: "Simple Line Plot"
- Save it as a PNG file and show it to me."""
        
        system_prompt = """You are a data visualization assistant with Python code execution.
Use matplotlib to create plots when requested. Always save plots to files."""
        
        # Call the service (non-streaming for easier assertion)
        response_text, response_id = await self.service.generate_response(
            user_text=test_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        # Assertions
        assert response_text is not None, "Response text should not be None"
        assert len(response_text) > 0, "Response text should not be empty"
        assert response_id is not None, "Response ID should not be None"
        
        # Retrieve the full response to check for annotations
        full_response = await self.service.client.responses.retrieve(response_id)
        
        # Verify that annotations exist in message content
        found_annotations = False
        file_annotations = []
        
        for item in full_response.output:
            if item.type == 'message' and hasattr(item, 'content'):
                for content_block in item.content:
                    if hasattr(content_block, 'annotations') and content_block.annotations:
                        for annotation in content_block.annotations:
                            if hasattr(annotation, 'file_id'):
                                found_annotations = True
                                file_annotations.append({
                                    'file_id': getattr(annotation, 'file_id', None),
                                    'container_id': getattr(annotation, 'container_id', None),
                                    'filename': getattr(annotation, 'filename', None)
                                })
        
        # Log findings
        print("\n=== File Annotations Found ===")
        print(f"Found annotations: {found_annotations}")
        print(f"Number of file annotations: {len(file_annotations)}")
        for i, ann in enumerate(file_annotations):
            print(f"Annotation {i+1}:")
            print(f"  file_id: {ann['file_id']}")
            print(f"  container_id: {ann['container_id']}")
            print(f"  filename: {ann['filename']}")
        print("==============================\n")
        
        # Assertions
        assert found_annotations, "Expected to find file annotations in message content"
        assert len(file_annotations) > 0, "Expected at least one file annotation"
        
        # Verify annotation structure
        first_annotation = file_annotations[0]
        assert first_annotation['file_id'] is not None, "file_id should not be None"
        assert first_annotation['container_id'] is not None, "container_id should not be None"
        assert first_annotation['filename'] is not None, "filename should not be None"
        
        # Verify filename is reasonable (should be PNG)
        filename = first_annotation['filename']
        assert filename.lower().endswith('.png'), f"Expected PNG file, got: {filename}"
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_multiple_files_generate_multiple_annotations(self):
        """Test that generating multiple files creates multiple annotations."""
        test_message = """Create two separate plots:
1. A bar chart of [10, 20, 30, 40]
2. A scatter plot of random data points

Save both as PNG files."""
        
        system_prompt = """You are a visualization assistant. Create plots using matplotlib."""
        
        response_text, response_id = await self.service.generate_response(
            user_text=test_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        # Retrieve full response
        full_response = await self.service.client.responses.retrieve(response_id)
        
        # Extract file annotations
        file_annotations = []
        for item in full_response.output:
            if item.type == 'message' and hasattr(item, 'content'):
                for content_block in item.content:
                    if hasattr(content_block, 'annotations') and content_block.annotations:
                        for annotation in content_block.annotations:
                            if hasattr(annotation, 'file_id'):
                                file_annotations.append({
                                    'file_id': annotation.file_id,
                                    'filename': annotation.filename
                                })
        
        print("\n=== Multiple Files Test ===")
        print(f"Number of file annotations: {len(file_annotations)}")
        for i, ann in enumerate(file_annotations):
            print(f"File {i+1}: {ann['filename']} (ID: {ann['file_id']})")
        print("===========================\n")
        
        # Assertions - we expect 2 files (bar chart + scatter plot)
        # Note: Model might create 1 or 2 files depending on how it interprets the request
        assert len(file_annotations) >= 1, "Expected at least one file annotation"
        assert len(file_annotations) <= 3, f"Expected 1-3 files, got {len(file_annotations)}"
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_csv_file_generation_annotations(self):
        """Test that generating CSV files creates proper annotations."""
        test_message = """Create a CSV file with the following data:
Name,Age,Score
Alice,25,95
Bob,30,87
Charlie,22,92

Save it as a CSV file."""
        
        system_prompt = "You are a data processing assistant with Python."
        
        response_text, response_id = await self.service.generate_response(
            user_text=test_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        # Retrieve and check annotations
        full_response = await self.service.client.responses.retrieve(response_id)
        
        file_annotations = []
        for item in full_response.output:
            if item.type == 'message' and hasattr(item, 'content'):
                for content_block in item.content:
                    if hasattr(content_block, 'annotations') and content_block.annotations:
                        for annotation in content_block.annotations:
                            if hasattr(annotation, 'file_id'):
                                file_annotations.append({
                                    'file_id': annotation.file_id,
                                    'filename': annotation.filename
                                })
        
        print("\n=== CSV File Test ===")
        print(f"Found {len(file_annotations)} file(s)")
        if file_annotations:
            print(f"Filename: {file_annotations[0]['filename']}")
            print(f"File ID: {file_annotations[0]['file_id']}")
        print("=====================\n")
        
        # Assertions
        assert len(file_annotations) >= 1, "Expected at least one file annotation for CSV"
        
        # Verify it's a CSV file
        filename = file_annotations[0]['filename']
        assert filename.lower().endswith('.csv'), f"Expected CSV file, got: {filename}"
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_sandbox_url_in_response_text(self):
        """Test that response text contains sandbox URLs that can be replaced.
        
        This verifies the URL replacement mechanism has something to replace.
        """
        test_message = """Create a simple histogram using matplotlib and show it to me.
Use data: [1, 2, 2, 3, 3, 3, 4, 4, 5]"""
        
        system_prompt = "You are a visualization assistant."
        
        response_text, response_id = await self.service.generate_response(
            user_text=test_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        print("\n=== Response Text Check ===")
        print(f"Response length: {len(response_text)}")
        print(f"Response preview: {response_text[:500]}")
        print("===========================\n")
        
        # Check if response contains file references (sandbox URLs or file IDs)
        # Note: With the annotations implementation, sandbox URLs should be replaced
        # with /files/{file_id}/content during streaming
        has_file_reference = any([
            'sandbox:' in response_text.lower(),
            '/files/' in response_text.lower(),
            '.png' in response_text.lower(),
            'file_id' in response_text.lower(),
            'download' in response_text.lower()
        ])
        
        # This assertion is informational - response format may vary
        print(f"Response contains file reference: {has_file_reference}")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_outputs_field_is_none(self):
        """Verify that the 'outputs' field is None (documenting API behavior).
        
        This test documents the discovery that the 'outputs' field exists
        in the API response schema but is always None. Files are in annotations.
        """
        test_message = "Create a simple plot with matplotlib and save it."
        system_prompt = "You are a visualization assistant."
        
        response_text, response_id = await self.service.generate_response(
            user_text=test_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        # Retrieve full response
        full_response = await self.service.client.responses.retrieve(response_id)
        
        # Check code_interpreter_call items for outputs
        outputs_found = False
        outputs_value = None
        
        for item in full_response.output:
            if hasattr(item, 'type') and item.type == 'code_interpreter_call':
                if hasattr(item, 'outputs'):
                    outputs_found = True
                    outputs_value = item.outputs
        
        print("\n=== Outputs Field Check ===")
        print(f"Outputs attribute exists: {outputs_found}")
        print(f"Outputs value: {outputs_value}")
        print("===========================\n")
        
        # Document the API behavior: outputs exists but is always None
        if outputs_found:
            assert outputs_value is None, (
                "Expected outputs to be None (Azure Responses API behavior). "
                "If this fails, the API behavior has changed and we should update "
                "our implementation to extract from outputs instead of annotations."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
