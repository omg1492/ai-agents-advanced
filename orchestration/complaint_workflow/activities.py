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
from models import ComplaintClassification, ComplaintExtraction, UserProfile

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


@activity.defn(name="extract_complaint_info")
async def extract_complaint_info_activity(message: str) -> ComplaintExtraction:
    """
    Extract structured information from complaint message using LLM.
    
    Args:
        message: Complaint message text to extract information from
    
    Returns:
        ComplaintExtraction with products, order_date, order_id, reason, evidence_provided
        (fields are None if not mentioned in the message)
    
    Activity configuration:
        - schedule_to_close_timeout: 30 seconds
        - retry_policy: max_attempts=3, initial_interval=1s, backoff=2.0
    """
    workflow_id = activity.info().workflow_id
    logger.info(f"ORCH_PHASE=extract workflow_id={workflow_id}")
    
    try:
        adapter = get_llm_adapter()
        extraction = await adapter.extract(
            text=message,
            response_schema=ComplaintExtraction
        )
        
        logger.info(
            f"ORCH_PHASE=extract_complete workflow_id={workflow_id} "
            f"order_id={extraction.order_id} "
            f"products={len(extraction.products_involved) if extraction.products_involved else 0} "
            f"has_reason={extraction.reason is not None}"
        )
        
        return extraction
    
    except Exception as e:
        logger.error(
            f"ORCH_PHASE=extract_error workflow_id={workflow_id} "
            f"error={str(e)}"
        )
        raise


@activity.defn(name="fetch_user_profile")
async def fetch_user_profile_activity(user_id: str) -> UserProfile:
    """
    Fetch user profile from user management system (mocked).
    
    This simulates calling an external user service API.
    In production, this would make HTTP calls to user management system.
    
    Args:
        user_id: User identifier to fetch profile for
    
    Returns:
        UserProfile with user attributes and scoring
    
    Activity configuration:
        - schedule_to_close_timeout: 30 seconds
        - retry_policy: max_attempts=3, initial_interval=1s, backoff=2.0
    """
    workflow_id = activity.info().workflow_id
    logger.info(f"ORCH_PHASE=fetch_user_profile workflow_id={workflow_id} user_id={user_id}")
    
    try:
        # Mock user profile generation based on user_id hash for consistency
        # In production, this would be: response = await http_client.get(f"/api/users/{user_id}")
        user_hash = hash(user_id) % 100
        
        # Determine segment (premium 20%, regular 50%, occasional 30%)
        if user_hash < 20:
            segment = "premium"
            loyalty_level = "platinum" if user_hash < 10 else "gold"
            user_score = 75.0 + (user_hash % 25)  # 75-100
            total_orders = 50 + (user_hash * 5)
            complaint_count = user_hash % 3
        elif user_hash < 70:
            segment = "regular"
            loyalty_level = "gold" if user_hash < 40 else "silver"
            user_score = 50.0 + (user_hash % 25)  # 50-75
            total_orders = 10 + (user_hash * 2)
            complaint_count = user_hash % 5
        else:
            segment = "occasional"
            loyalty_level = "silver" if user_hash < 85 else "bronze"
            user_score = 25.0 + (user_hash % 25)  # 25-50
            total_orders = user_hash % 15
            complaint_count = user_hash % 8
        
        # Mock cities and countries
        cities = ["Prague", "Berlin", "Paris", "Vienna", "Amsterdam", "Brussels", "Warsaw", "Budapest"]
        countries = ["Czech Republic", "Germany", "France", "Austria", "Netherlands", "Belgium", "Poland", "Hungary"]
        location_idx = user_hash % len(cities)
        
        profile = UserProfile(
            user_id=user_id,
            segment=segment,
            loyalty_level=loyalty_level,
            city=cities[location_idx],
            country=countries[location_idx],
            user_score=user_score,
            total_orders=total_orders,
            complaint_count=complaint_count
        )
        
        logger.info(
            f"ORCH_PHASE=fetch_user_profile_complete workflow_id={workflow_id} "
            f"user_id={user_id} segment={profile.segment} loyalty={profile.loyalty_level} "
            f"score={profile.user_score:.1f} orders={profile.total_orders} complaints={profile.complaint_count}"
        )
        
        return profile
    
    except Exception as e:
        logger.error(
            f"ORCH_PHASE=fetch_user_profile_error workflow_id={workflow_id} "
            f"user_id={user_id} error={str(e)}"
        )
        raise


# Activity execution configuration for Temporal
ACTIVITY_TIMEOUT = timedelta(seconds=30)
ACTIVITY_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0
)
