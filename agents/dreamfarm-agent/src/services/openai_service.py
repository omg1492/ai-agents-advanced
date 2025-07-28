"""OpenAI service for handling AI interactions."""

import os
import logging
from typing import Optional

from openai import OpenAI, AzureOpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI or Azure OpenAI API.
    
    Supports both OpenAI API and Azure OpenAI Service through environment
    variable configuration.
    """
    
    def __init__(self):
        """Initialize the OpenAI service with appropriate client."""
        self.client = self._get_openai_client()
        self.model_name = self._get_model_name()
        logger.info(f"Initialized OpenAI service with provider: {os.getenv('OPENAI_API_TYPE', 'azure')}")
    
    def _get_openai_client(self) -> OpenAI | AzureOpenAI:
        """Get the appropriate OpenAI client based on configuration.
        
        Returns:
            OpenAI or AzureOpenAI client instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        api_type = os.getenv("OPENAI_API_TYPE", "azure")
        
        if api_type == "azure":
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION")
            
            if not all([endpoint, api_key, api_version]):
                raise ValueError("Missing required Azure OpenAI environment variables")
            
            return AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version
            )
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OPENAI_API_KEY environment variable")
                
            return OpenAI(api_key=api_key)
    
    def _get_model_name(self) -> str:
        """Get the model name based on the provider configuration.
        
        Returns:
            Model name to use for completions
        """
        api_type = os.getenv("OPENAI_API_TYPE", "azure")
        
        if api_type == "azure":
            model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            if not model:
                raise ValueError("Missing AZURE_OPENAI_DEPLOYMENT_NAME environment variable")
            return model
        else:
            return os.getenv("OPENAI_MODEL", "gpt-4.1")
    
    async def generate_response(self, messages: list, system_prompt: Optional[str] = None) -> str:
        """Generate a response using the OpenAI API.
        
        Args:
            messages: List of conversation messages
            system_prompt: Optional system prompt to set context
            
        Returns:
            Generated response from the AI model
            
        Raises:
            Exception: If the API call fails
        """
        try:
            # Prepare messages with system prompt if provided
            api_messages = []
            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})
            api_messages.extend(messages)
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=api_messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise
