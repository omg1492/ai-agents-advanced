"""
Temporal activities for complaint workflow.

Each activity represents a side-effect operation (LLM call, data fetch, etc.)
isolated from workflow determinism. Activities can be retried and have timeouts.
"""

import logging
from datetime import timedelta

from temporalio import activity
from temporalio.common import RetryPolicy

from llm_adapter import get_llm_adapter
from models import ComplaintClassification

logger = logging.getLogger(__name__)


@activity.defn(name="classify_complaint")
async def classify_complaint_activity(message: str) -> ComplaintClassification:
    """
    Classify whether input message is a complaint using LLM structured output.
    
    Args:
        message: User input message to classify
    
    Returns:
        ComplaintClassification with is_complaint and confidence
    
    Activity configuration:
        - schedule_to_close_timeout: 30 seconds
        - retry_policy: max_attempts=3, initial_interval=1s, backoff=2.0
    """
    workflow_id = activity.info().workflow_id
    logger.info(f"ORCH_PHASE=classify workflow_id={workflow_id}")
    
    try:
        adapter = get_llm_adapter()
        classification = await adapter.classify(
            text=message,
            response_schema=ComplaintClassification
        )
        
        logger.info(
            f"ORCH_PHASE=classify_complete workflow_id={workflow_id} "
            f"is_complaint={classification.is_complaint} "
            f"confidence={classification.confidence:.2f}"
        )
        
        return classification
    
    except Exception as e:
        logger.error(
            f"ORCH_PHASE=classify_error workflow_id={workflow_id} "
            f"error={str(e)}"
        )
        raise


# Activity execution configuration for Temporal
ACTIVITY_TIMEOUT = timedelta(seconds=30)
ACTIVITY_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0
)
