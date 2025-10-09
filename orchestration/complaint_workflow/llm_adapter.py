"""
Azure OpenAI integration for complaint classification activity.

Implements structured outputs using Responses API with Pydantic schemas.
Follows agent patterns from Design.md with async client, error handling, and configurable API versions.
"""

import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from openai.types.shared_params import Reasoning
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMAdapter:
    """
    Azure OpenAI client adapter for complaint workflow LLM activities.
    
    Uses Responses API (responses.parse) with structured outputs and reasoning.
    Uses unified OpenAI v1 API pattern (same as agent).
    """
    
    def __init__(self):
        """Initialize Azure OpenAI client from environment variables."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        self.api_version = os.getenv("OPENAI_API_VERSION", "preview")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5")
        self.reasoning_effort = os.getenv("REASONING_EFFORT", "minimal")
        
        if not self.api_key or not self.base_url:
            raise ValueError(
                "OPENAI_API_KEY and OPENAI_BASE_URL required in .env file"
            )
        
        # Initialize async OpenAI client with unified v1 API pattern (matches agent)
        # For Azure: base_url should end with /openai/v1/
        # API version is passed via default_query parameter
        default_query = {"api-version": self.api_version} if self.api_version else None
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_query=default_query
        )
        logger.info(
            f"LLM adapter initialized: model={self.model}, "
            f"base_url={self.base_url}, api_version={self.api_version}, "
            f"reasoning_effort={self.reasoning_effort}"
        )
    
    async def classify(
        self,
        text: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """
        Classify text using Responses API with structured output (Pydantic schema).
        
        Args:
            text: Input text to classify
            response_schema: Pydantic model defining expected response structure
        
        Returns:
            Instance of response_schema with parsed structured output from responses.parse
        
        Raises:
            ValueError: If response parsing fails
        """
        system_prompt = """You are a complaint classification system.
Analyze the input text and determine:
1. Is this a complaint? (customer expressing dissatisfaction, reporting problem, requesting resolution)
2. Confidence level (0.0-1.0)

A complaint is when a customer reports a problem, expresses dissatisfaction, or requests resolution for an issue.

NOT complaints: general questions, order inquiries, product availability requests, general information seeking."""
        
        try:
            # Use Responses API with structured outputs (text_format)
            # Reference: https://platform.openai.com/docs/guides/structured-outputs
            response = await self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                text_format=response_schema,
                reasoning=Reasoning(effort=self.reasoning_effort)
            )
            
            # Parse structured output
            if not response.output_parsed:
                raise ValueError("No parsed output in response")
            
            result = response.output_parsed
            
            logger.info(
                f"Classification completed: is_complaint={result.is_complaint}, "
                f"confidence={result.confidence:.2f}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            raise ValueError(f"Classification failed: {str(e)}") from e
    
    async def extract(
        self,
        text: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """
        Extract structured information from text using Responses API.
        
        Args:
            text: Input text to extract information from
            response_schema: Pydantic model defining expected response structure
        
        Returns:
            Instance of response_schema with extracted information
        
        Raises:
            ValueError: If response parsing fails
        """
        system_prompt = """You are an information extraction system for customer complaints.
Extract the following information from the complaint message if present:
- Products involved (list of product names/types mentioned)
- Order date (convert to YYYY-MM-DD format if possible)
- Order ID (any order number or identifier mentioned)
- Reason for complaint (brief summary of the main issue)
- Evidence provided (mention of photos, receipts, attachments, etc.)

Important rules:
1. Only extract information that is explicitly mentioned in the message
2. If information is not present, set the field to null
3. For order dates, try to standardize to YYYY-MM-DD format
4. For products, extract specific product names if mentioned
5. Keep the reason concise but descriptive"""
        
        try:
            # Use Responses API with structured outputs
            response = await self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                text_format=response_schema,
                reasoning=Reasoning(effort=self.reasoning_effort)
            )
            
            # Parse structured output
            if not response.output_parsed:
                raise ValueError("No parsed output in response")
            
            result = response.output_parsed
            
            logger.info(
                f"Extraction completed: order_id={result.order_id}, "
                f"products={len(result.products_involved) if result.products_involved else 0}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Extraction error: {e}", exc_info=True)
            raise ValueError(f"Extraction failed: {str(e)}") from e


# Singleton instance (lazy initialization)
_adapter: Optional[LLMAdapter] = None


def get_llm_adapter() -> LLMAdapter:
    """Get or create singleton LLM adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter()
    return _adapter
