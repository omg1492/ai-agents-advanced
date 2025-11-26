"""
Azure OpenAI integration for complaint classification activity.

Implements structured outputs using Responses API with Pydantic schemas.
Follows agent patterns from Design.md with async client, error handling, and configurable API versions.
"""

import logging
import os
from typing import Optional, TYPE_CHECKING

from openai import AsyncOpenAI
from openai.types.shared_params import Reasoning
from pydantic import BaseModel

if TYPE_CHECKING:
    from models import Action

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
    
    def _log_reasoning_usage(self, response, phase: str):
        """
        Log reasoning token usage from response.
        
        Note: OpenAI Responses API with text_format does not expose reasoning text.
        The reasoning happens internally (visible in usage.reasoning_tokens) but
        the actual reasoning chain is not accessible via the API.
        """
        if self.reasoning_effort != "minimal":
            try:
                usage = response.usage
                reasoning_tokens = getattr(getattr(usage, 'output_tokens_details', None), 'reasoning_tokens', 0) if usage else 0
                if reasoning_tokens > 0:
                    logger.info(f"💭 Reasoning ({phase}): {reasoning_tokens} tokens (internal only)")
            except Exception:
                pass  # Silently ignore if usage data unavailable
    
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
            
            self._log_reasoning_usage(response, "classify")
            
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
            
            self._log_reasoning_usage(response, "extract")
            
            logger.info(
                f"Extraction completed: order_id={result.order_id}, "
                f"products={len(result.products_involved) if result.products_involved else 0}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Extraction error: {e}", exc_info=True)
            raise ValueError(f"Extraction failed: {str(e)}") from e
    
    async def decide(
        self,
        context: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """
        Decide complaint validity using policy-based reasoning with few-shot examples.
        
        Args:
            context: Formatted context including complaint details and user profile
            response_schema: Pydantic model defining expected response structure
        
        Returns:
            Instance of response_schema with decision (action, reason, confidence)
        
        Raises:
            ValueError: If response parsing fails
        """
        system_prompt = """You are a complaint validation system for a farm-to-table food marketplace.

COMPANY POLICY - Farmer Product Complaints:

AUTO-APPROVE (VALID) when:
✓ Clear product quality issues (spoiled, rotten, moldy, contaminated)
✓ Physical damage during delivery (broken, crushed, leaking)
✓ Missing items from order
✓ Wrong items delivered
✓ Food safety concerns (mold, contamination, foreign objects)
✓ Evidence provided (photos, receipts) strengthens case
✓ User has good history (score >40, low complaint rate)

AUTO-REJECT (NOT_VALID) when:
✗ Subjective taste preferences ("didn't taste as expected")
✗ Natural product variations (size, color, ripeness within normal range)
✗ User error (ordered wrong item, didn't refrigerate properly)
✗ Unreasonable timeframe (complaint about order from months ago)
✗ Suspicious pattern (very low user score <25, high complaint rate relative to orders)
✗ Vague or no specific issue described
✗ Abusive or threatening language

ESCALATE TO HUMAN (HUMAN_REVIEW) when:
⚠ Borderline quality issues (slightly wilted but usable)
⚠ High-value claims without evidence
⚠ Premium customers (platinum/gold) with edge-case issues
⚠ Complex cases involving multiple products with mixed issues
⚠ Unclear or contradictory information
⚠ Medium user scores (25-40) with unusual patterns
⚠ Legal or health implications mentioned

FEW-SHOT EXAMPLES:

Example 1 - VALID:
Context: Organic tomatoes arrived completely rotten and moldy. Photos attached. User: Gold loyalty, score 72, 45 orders, 1 complaint.
Decision: VALID
Reason: Clear food quality issue (rotten/moldy produce) with evidence. Good customer history. Auto-approve refund/replacement.
Confidence: 0.95

Example 2 - NOT_VALID:
Context: Apples were smaller than expected. No evidence. User: Bronze loyalty, score 22, 8 orders, 5 complaints.
Decision: NOT_VALID
Reason: Natural size variation is normal for fresh produce. High complaint rate (62.5%) with low user score suggests pattern of unreasonable complaints. No safety or quality defect.
Confidence: 0.92

Example 3 - HUMAN_REVIEW:
Context: Cheese has slight discoloration, might be mold or natural aging. No photo. User: Platinum loyalty, score 88, 120 orders, 2 complaints.
Decision: HUMAN_REVIEW
Reason: Borderline case - discoloration could be normal aging or quality issue. Premium customer with excellent history warrants human judgment. Needs expert assessment.
Confidence: 0.78

Example 4 - VALID:
Context: Jar of honey arrived broken, glass shards in packaging. Photo provided. User: Silver loyalty, score 55, 23 orders, 0 complaints.
Decision: VALID
Reason: Clear damage during delivery with safety concern (broken glass). Evidence provided. First-time complaint from regular customer. Auto-approve.
Confidence: 0.98

Example 5 - HUMAN_REVIEW:
Context: Mixed vegetables order - carrots good but lettuce slightly wilted. User: Gold loyalty, score 67, 34 orders, 3 complaints.
Decision: HUMAN_REVIEW
Reason: Mixed issue (partial order problem). "Slightly wilted" is borderline - might be usable. Good customer but moderate complaint rate. Human should assess partial refund vs full refund.
Confidence: 0.73

Example 6 - NOT_VALID:
Context: Bread doesn't taste as good as last time, seems different recipe. User: Regular segment, score 31, 12 orders, 4 complaints.
Decision: NOT_VALID
Reason: Subjective taste preference, not a quality or safety defect. Artisan products naturally vary. User has high complaint rate (33%). Reject and provide education on product variability.
Confidence: 0.89

DECISION GUIDELINES:
- Prioritize food safety and clear quality defects
- Evidence (photos, receipts) increases confidence
- User history matters: good customers (score >60) get benefit of doubt
- Problematic users (score <30, complaints >30% of orders) require scrutiny
- When uncertain, escalate to human (confidence <0.80)
- Premium customers (platinum/gold) with edge cases deserve human attention
- Be fair but protect business from abuse

Analyze the complaint context and make a decision."""
        
        try:
            # Use Responses API with structured outputs
            response = await self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                text_format=response_schema,
                reasoning=Reasoning(effort=self.reasoning_effort)
            )
            
            # Parse structured output
            if not response.output_parsed:
                raise ValueError("No parsed output in response")
            
            result = response.output_parsed
            
            self._log_reasoning_usage(response, "decide")
            
            logger.info(
                f"Decision completed: action={result.action}, "
                f"confidence={result.confidence:.2f}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Decision error: {e}", exc_info=True)
            raise ValueError(f"Decision failed: {str(e)}") from e
    
    async def generate_user_message(
        self,
        action: "Action",
        context: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """
        Generate user-facing message for VALID or NOT_VALID decisions.
        
        Args:
            action: Decision action (VALID or NOT_VALID)
            context: Formatted context including decision and complaint details
            response_schema: Pydantic model for UserMessage
        
        Returns:
            UserMessage with subject, message content, and tone
        
        Raises:
            ValueError: If response parsing fails
        """
        if action.value == "VALID":
            system_prompt = """You are a customer service message generator for a farm-to-table marketplace.

Generate an apologetic, professional message for an APPROVED complaint.

INSTRUCTIONS FOR VALID (APPROVED) COMPLAINTS:
✓ Start with sincere apology for the issue
✓ Acknowledge the specific problem (broken items, spoiled produce, etc.)
✓ Confirm we take full responsibility
✓ State clear resolution: full refund OR replacement (your choice based on context)
✓ Mention timeframe (refund in 3-5 business days, replacement shipped within 24 hours)
✓ Thank customer for bringing this to attention
✓ Emphasize quality commitment
✓ For premium customers (gold/platinum), add extra gesture (discount on next order)
✓ Warm, empathetic tone but remain professional

TONE: Apologetic, empathetic, solution-focused
SUBJECT: Should be concise and positive (e.g., "We're Taking Care of This")
MESSAGE: 3-5 paragraphs, warm but professional

Example:
Subject: We're Sorry - Your Refund is Processed
Message: Dear Valued Customer, We sincerely apologize for receiving damaged products...

Generate the message now."""

        else:  # NOT_VALID
            system_prompt = """You are a customer service message generator for a farm-to-table marketplace.

Generate a firm but respectful message for a REJECTED complaint.

INSTRUCTIONS FOR NOT_VALID (REJECTED) COMPLAINTS:
✗ Be respectful and professional, never dismissive
✗ Explain the reason for rejection clearly (reference policy)
✗ If applicable, educate about natural product variation
✗ Specify what additional information could lead to reconsideration:
  - Photos showing the actual issue
  - More specific description of the problem
  - Order details for verification
✗ Provide alternative options (exchange guidelines, quality standards)
✗ Invite them to contact customer service if they have questions
✗ Keep door open for legitimate future complaints

TONE: Professional, firm, educational (not cold or dismissive)
SUBJECT: Clear but not harsh (e.g., "Regarding Your Recent Inquiry")
MESSAGE: 3-4 paragraphs, maintain respect while being clear

Example:
Subject: Regarding Your Recent Inquiry
Message: Thank you for contacting us. After reviewing your case, we found that...

Generate the message now."""

        try:
            response = await self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                text_format=response_schema,
                reasoning=Reasoning(effort=self.reasoning_effort)
            )
            
            if not response.output_parsed:
                raise ValueError("No parsed output in response")
            
            result = response.output_parsed
            
            self._log_reasoning_usage(response, "generate_message")
            
            logger.info(f"User message generated: tone={result.tone}")
            
            return result
        
        except Exception as e:
            logger.error(f"User message generation error: {e}", exc_info=True)
            raise ValueError(f"User message generation failed: {str(e)}") from e
    
    async def generate_review_packet(
        self,
        context: str,
        response_schema: type[BaseModel]
    ) -> BaseModel:
        """
        Generate structured review packet for human evaluation of escalated complaints.
        
        Args:
            context: Formatted context including decision reason and full complaint details
            response_schema: Pydantic model for ReviewPacket
        
        Returns:
            ReviewPacket with structured review information
        
        Raises:
            ValueError: If response parsing fails
        """
        system_prompt = """You are a case preparation assistant for human reviewers in a complaint handling system.

Generate a structured review packet for HUMAN_REVIEW (escalated) cases.

INSTRUCTIONS:
1. SUMMARY: Write 2-3 sentences summarizing the core issue and why it's borderline
2. ARGUMENTS FOR APPROVAL: List 3-5 specific points supporting the customer's claim
   - Product quality issues mentioned
   - Customer history (good score, low complaint rate)
   - Evidence provided
   - Safety concerns
   - Premium customer status
3. ARGUMENTS AGAINST APPROVAL: List 3-5 specific points suggesting rejection
   - Vague descriptions
   - Lack of evidence
   - Suspicious patterns in customer behavior
   - Subjective preferences vs. defects
   - Policy boundaries
4. RECOMMENDED ACTION: Your suggested decision with 2-3 sentence reasoning
   Options: "Approve with full refund", "Approve with partial refund", "Approve with replacement only", "Reject with explanation", "Request additional information"
5. PRIORITY: 
   - high: Food safety, premium customers, time-sensitive
   - medium: Standard quality issues, moderate value
   - low: Minor issues, low-value items
6. CUSTOMER CONTEXT: Relevant background on customer (segment, loyalty, history)

TONE: Objective, balanced, analytical
FORMAT: Professional internal document for decision-maker

The review packet should enable a human to quickly understand the situation and make an informed decision."""

        try:
            response = await self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                text_format=response_schema,
                reasoning=Reasoning(effort=self.reasoning_effort)
            )
            
            if not response.output_parsed:
                raise ValueError("No parsed output in response")
            
            result = response.output_parsed
            
            self._log_reasoning_usage(response, "generate_review")
            
            logger.info(f"Review packet generated: priority={result.priority}")
            
            return result
        
        except Exception as e:
            logger.error(f"Review packet generation error: {e}", exc_info=True)
            raise ValueError(f"Review packet generation failed: {str(e)}") from e


# Singleton instance (lazy initialization)
_adapter: Optional[LLMAdapter] = None


def get_llm_adapter() -> LLMAdapter:
    """Get or create singleton LLM adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter()
    return _adapter
