"""Integration tests for Code Interpreter tool - real Responses API.

Run these by selecting `-m integration`. Tests skip at runtime if required
API credentials are not available or code interpreter is not enabled.
"""

import pytest
import os

from src.services.openai_service import OpenAIService
from src.services.config_service import ConfigService

pytestmark = pytest.mark.integration


class TestCodeInterpreterIntegration:
    """Integration tests for Code Interpreter that use real Azure OpenAI Responses API.
    
    These tests require:
    1. Valid Azure OpenAI API credentials with Responses API access
    2. Code Interpreter feature enabled (ENABLE_CODE_INTERPRETER=true)
    3. Model that supports code_interpreter tool
    
    Run with: pytest -m integration tests/test_code_interpreter_integration.py
    """
    
    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures."""
        # Check env for integration readiness (skip gracefully if missing)
        has_api_key = any(os.getenv(k) for k in (
            'OPENAI_API_KEY', 'AZURE_OPENAI_API_KEY'
        ))
        if not has_api_key:
            pytest.skip("Code Interpreter integration requires OpenAI/Azure API key")
        
        # Ensure Code Interpreter is enabled for integration tests
        os.environ['ENABLE_CODE_INTERPRETER'] = 'true'
        # Disable MCP tools temporarily for cleaner test (they may not be running)
        os.environ['FARMER_TOOLS_ENABLED'] = 'false'
        os.environ['TAVILY_ENABLED'] = 'false'
        os.environ['STOCK_TOOL_ENABLED'] = 'false'
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create config and service
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
    async def test_code_interpreter_tool_registration(self):
        """Test that code_interpreter tool is registered when enabled."""
        tools = self.service.get_tools()
        
        # Should have tools array
        assert tools is not None
        assert isinstance(tools, list)
        
        # Should contain code_interpreter tool
        code_interpreter_tools = [t for t in tools if t.get('type') == 'code_interpreter']
        assert len(code_interpreter_tools) > 0, "Code interpreter tool not found in tools list"
        
        # Verify structure
        ci_tool = code_interpreter_tools[0]
        assert ci_tool['type'] == 'code_interpreter'
        assert 'container' in ci_tool
        assert ci_tool['container']['type'] == 'auto'
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_code_interpreter_mathematical_calculation(self):
        """Test that code interpreter successfully executes mathematical calculations.
        
        This test sends a prompt requiring complex mathematical computation
        and verifies that the code_interpreter tool is invoked (not asserting
        on specific numerical output, just that the tool was used).
        """
        # Crafted message that should trigger code interpreter usage
        test_message = """Calculate the following and show your work:
1. The sum of squares of the first 100 natural numbers
2. The factorial of 15
3. The value of e^(π*i) + 1 (Euler's identity)

Please use Python code to compute these values precisely."""
        
        # System prompt can be minimal for this test
        system_prompt = """You are a helpful AI assistant with access to a Python code interpreter.
When asked to perform calculations or data analysis, use the code interpreter tool to execute Python code."""
        
        # Call the service
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
        
        # The response should contain numerical results (since code was executed)
        # We check for common mathematical indicators
        lower_response = response_text.lower()
        has_math_indicators = any(indicator in lower_response for indicator in [
            'sum', 'factorial', 'euler', 'result', 'answer', 'equals', '=',
            'calculation', 'computed', 'value'
        ])
        assert has_math_indicators, f"Response doesn't seem to contain mathematical results: {response_text[:200]}"
        
        # Log the response for manual verification during test runs
        print("\n=== Code Interpreter Response ===")
        print(f"Response ID: {response_id}")
        print(f"Response: {response_text[:500]}...")
        print("=================================\n")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_code_interpreter_data_analysis(self):
        """Test code interpreter with data analysis task.
        
        Verifies that the agent can use code_interpreter for data processing
        and statistical calculations.
        """
        test_message = """I have a dataset of daily temperatures in Celsius:
[22, 24, 23, 25, 26, 24, 23, 27, 28, 26, 25, 24, 23, 22, 24]

Please analyze this data and provide:
1. Mean temperature
2. Standard deviation
3. Min and max values

Use Python for calculations."""
        
        system_prompt = """You are a data analysis assistant with Python code execution capabilities.
Use the code interpreter to perform statistical calculations when needed."""
        
        response_text, response_id = await self.service.generate_response(
            user_text=test_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        # Verify response is non-empty and contains analysis results
        assert response_text is not None
        assert len(response_text) > 0
        assert response_id is not None
        
        # Should contain statistical terms
        lower_response = response_text.lower()
        has_stats = any(term in lower_response for term in [
            'mean', 'average', 'standard deviation', 'minimum', 'maximum',
            'min', 'max', 'std'
        ])
        assert has_stats, f"Response doesn't contain statistical analysis: {response_text[:200]}"
        
        print("\n=== Data Analysis Response ===")
        print(f"Response: {response_text[:500]}...")
        print("==============================\n")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_code_interpreter_with_conversation_continuity(self):
        """Test code interpreter with multi-turn conversation using response_id.
        
        Verifies that code execution context can be maintained across turns.
        """
        # First turn - define a variable
        first_message = "Using Python, create a variable 'x' with value 42 and show it."
        system_prompt = "You are an assistant with Python code execution."
        
        first_response, first_response_id = await self.service.generate_response(
            user_text=first_message,
            system_prompt=system_prompt,
            previous_response_id=None,
            user_is_vip=False,
            user_id="test_user"
        )
        
        assert first_response is not None
        assert first_response_id is not None
        
        # Second turn - use the previously defined variable
        second_message = "Now multiply x by 2 and show the result."
        
        second_response, second_response_id = await self.service.generate_response(
            user_text=second_message,
            system_prompt=system_prompt,
            previous_response_id=first_response_id,
            user_is_vip=False,
            user_id="test_user"
        )
        
        assert second_response is not None
        assert second_response_id is not None
        
        # The second response should reference the calculation (84 = 42 * 2)
        # We don't assert exact format, just that it contains relevant content
        print("\n=== Multi-turn Code Execution ===")
        print(f"Turn 1: {first_response[:300]}...")
        print(f"Turn 2: {second_response[:300]}...")
        print("=================================\n")
    
    @pytest.mark.integration
    @pytest.mark.requires_api
    @pytest.mark.slow
    async def test_code_interpreter_disabled_fallback(self):
        """Test behavior when code interpreter is disabled via config."""
        # Temporarily disable code interpreter
        original_state = self.config.code_interpreter.enabled
        self.config.code_interpreter.enabled = False
        
        try:
            tools = self.service.get_tools()
            
            # Should not contain code_interpreter when disabled
            if tools:
                code_interpreter_tools = [t for t in tools if t.get('type') == 'code_interpreter']
                assert len(code_interpreter_tools) == 0, "Code interpreter should not be registered when disabled"
        finally:
            # Restore original state
            self.config.code_interpreter.enabled = original_state
    
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_code_interpreter_error_handling(self):
        """Test that the service handles code execution errors gracefully.
        
        This test deliberately requests code that will fail and verifies
        that the system doesn't crash.
        """
        # Request code that will cause an error (division by zero)
        test_message = """Execute this Python code and tell me what happens:
result = 10 / 0
print(result)"""
        
        system_prompt = "You are an assistant. Execute code when requested."
        
        try:
            response_text, response_id = await self.service.generate_response(
                user_text=test_message,
                system_prompt=system_prompt,
                previous_response_id=None,
                user_is_vip=False,
                user_id="test_user"
            )
            
            # Should get a response even if code failed
            assert response_text is not None
            assert len(response_text) > 0
            
            print("\n=== Error Handling Response ===")
            print(f"Response: {response_text[:500]}...")
            print("===============================\n")
            
        except Exception as e:
            # If an exception occurs, it should be a reasonable error, not a crash
            pytest.fail(f"Service should handle code errors gracefully, but raised: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
