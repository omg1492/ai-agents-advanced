"""Custom Azure OpenAI LLM wrapper for DeepEval evaluation.

This module provides a DeepEval-compatible wrapper for Azure OpenAI models,
allowing seamless integration with our existing unified OpenAI/Azure SDK setup.
"""
from openai import AsyncOpenAI
from deepeval.models.base_model import DeepEvalBaseLLM
from pydantic import BaseModel


class AzureOpenAIEvaluator(DeepEvalBaseLLM):
    """Custom Azure OpenAI model for DeepEval metrics evaluation.
    
    Uses the unified OpenAI SDK client that supports both OpenAI and Azure OpenAI
    with the same interface. This ensures compatibility with the existing agent
    configuration and matches the pattern used in openai_service.py.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        api_version: str,
        model: str = "gpt-5"
    ):
        """Initialize the Azure OpenAI evaluator using unified SDK format.
        
        Args:
            api_key: Azure OpenAI API key
            base_url: Azure OpenAI endpoint in unified format (e.g., https://xxx.openai.azure.com/openai/v1/)
            api_version: Azure OpenAI API version
            model: Model deployment name (default: gpt-5)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.model_name = model
        
        # Use unified AsyncOpenAI client (same as agent's openai_service.py)
        # with default_query for API version (Azure OpenAI requirement)
        default_query = {"api-version": api_version} if base_url else None
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_query=default_query
        )

    def load_model(self):
        """Return the client instance (required by DeepEval)."""
        return self.client

    def generate(self, prompt: str, schema: BaseModel | None = None) -> str | BaseModel:
        """Synchronous generation (wraps async for compatibility).
        
        Args:
            prompt: Text prompt for the model
            schema: Optional Pydantic schema for structured output
            
        Returns:
            Generated text or structured object
        """
        import asyncio
        
        # Run async method in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.a_generate(prompt, schema))

    async def a_generate(self, prompt: str, schema: BaseModel | None = None) -> str | BaseModel:
        """Asynchronous generation method using Responses API.
        
        Args:
            prompt: Text prompt for the model
            schema: Optional Pydantic schema for structured output
            
        Returns:
            Generated text or structured object (if schema provided)
        """
        client = self.load_model()
        
        # Use Responses API (modern, same as agent)
        try:
            if schema is not None:
                # Get the schema and ensure additionalProperties is false recursively
                # (required by Azure OpenAI for structured output)
                json_schema = schema.model_json_schema()
                self._add_additional_properties_false(json_schema)
                
                # Create response with structured output via response_format
                response = await client.responses.create(
                    model=self.model_name,
                    input=prompt,
                    response_format={"type": "json_schema", "json_schema": {
                        "name": "evaluation_output",
                        "schema": json_schema,
                        "strict": True
                    }},
                    store=False,  # Don't store evaluation queries
                )
                
                # Parse JSON response and return as Pydantic model
                import json
                output_text = getattr(response, "output_text", None) or ""
                if output_text:
                    json_data = json.loads(output_text)
                    return schema(**json_data)
                else:
                    # Fallback: return empty schema
                    return schema()
            else:
                # Standard text generation without schema
                response = await client.responses.create(
                    model=self.model_name,
                    input=prompt,
                    store=False,  # Don't store evaluation queries
                )
                
                return getattr(response, "output_text", None) or ""
                
        except TypeError as e:
            # Expected: Responses API doesn't support response_format parameter
            # This is normal when DeepEval requests structured output - we gracefully fall back
            import logging
            logging.debug(f"Responses API fallback (expected): {e}")
            # DeepEval will retry without response_format or use text parsing
            raise
        except Exception as e:
            # Log unexpected errors and re-raise for DeepEval to handle
            import logging
            logging.error(f"Unexpected Responses API error: {e}")
            raise
    
    @staticmethod
    def _add_additional_properties_false(schema_dict: dict) -> None:
        """Recursively add additionalProperties: false to all object schemas.
        
        Azure OpenAI requires this for structured output with strict mode.
        """
        if isinstance(schema_dict, dict):
            # If this is an object type, add additionalProperties: false
            if schema_dict.get("type") == "object":
                schema_dict["additionalProperties"] = False
            
            # Recurse into all dict values
            for value in schema_dict.values():
                if isinstance(value, dict):
                    AzureOpenAIEvaluator._add_additional_properties_false(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            AzureOpenAIEvaluator._add_additional_properties_false(item)

    def get_model_name(self) -> str:
        """Return model name for DeepEval reporting."""
        return f"Azure OpenAI {self.model_name}"
