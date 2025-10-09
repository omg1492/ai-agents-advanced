"""
Temporal workflow for complaint handling.

Orchestrates classification, field validation, data fetching, decision-making,
and resolution activities. Maintains determinism by delegating side-effects to activities.
"""

from temporalio import workflow

from activities import (
    classify_complaint_activity,
    extract_complaint_info_activity,
    fetch_user_profile_activity,
    decide_complaint_validity_activity,
    ACTIVITY_TIMEOUT,
    ACTIVITY_RETRY_POLICY
)
from models import ComplaintIn, TerminalStatus, WorkflowResult

# Task queue constant (shared with worker)
TASK_QUEUE_NAME = "complaint-workflow-queue"


@workflow.defn
class ComplaintWorkflow:
    """
    Durable complaint handling workflow.
    
    Phases:
    1. Classification (is_complaint?)
    2. Field sufficiency check (has required identifiers?)
    3. Data fetch (order + user profile)
    4. Decision (VALID / NOT_VALID / HUMAN_REVIEW)
    5. Resolution (user message or review packet)
    """
    
    @workflow.run
    async def run(self, complaint: ComplaintIn) -> WorkflowResult:
        """
        Execute complaint resolution workflow.
        
        Args:
            complaint: Input complaint with message and user_id
        
        Returns:
            WorkflowResult with terminal status and outcome details
        """
        workflow_id = workflow.info().workflow_id
        
        workflow.logger.info(
            f"Starting complaint workflow: {workflow_id}, "
            f"user={complaint.user_id}, "
            f"message_len={len(complaint.message)}"
        )
        
        # Phase 1: Classify complaint
        classification = await workflow.execute_activity(
            classify_complaint_activity,
            complaint.message,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )
        
        # Branch: Not a complaint → short exit
        if not classification.is_complaint:
            workflow.logger.info(
                f"Not a complaint: {workflow_id}, "
                f"confidence={classification.confidence:.2f}"
            )
            return WorkflowResult(
                complaint_id=workflow_id,
                terminal_status=TerminalStatus.COMPLETED,
                reason="NOT_COMPLAINT",
                user_message="Thank you for your inquiry. This doesn't appear to be a complaint. "
                             "For product questions or orders, please visit our help center."
            )
        
        # Branch: Is a complaint → continue processing
        workflow.logger.info(
            f"Confirmed complaint: {workflow_id}, "
            f"confidence={classification.confidence:.2f}"
        )
        
        # Phase 2: Extract complaint information
        extraction = await workflow.execute_activity(
            extract_complaint_info_activity,
            complaint.message,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )
        
        workflow.logger.info(
            f"Extracted info: {workflow_id}, "
            f"order_id={extraction.order_id}, "
            f"products={extraction.products_involved}, "
            f"reason={extraction.reason}"
        )
        
        # Phase 3: Fetch user profile
        user_profile = await workflow.execute_activity(
            fetch_user_profile_activity,
            complaint.user_id,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )
        
        workflow.logger.info(
            f"Fetched user profile: {workflow_id}, "
            f"user_id={user_profile.user_id}, segment={user_profile.segment}, "
            f"loyalty={user_profile.loyalty_level}, score={user_profile.user_score:.1f}, "
            f"orders={user_profile.total_orders}, complaints={user_profile.complaint_count}"
        )
        
        # Phase 4: Decide complaint validity
        decision = await workflow.execute_activity(
            decide_complaint_validity_activity,
            args=[extraction, user_profile],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )
        
        workflow.logger.info(
            f"Decision made: {workflow_id}, "
            f"action={decision.action}, confidence={decision.confidence:.2f}, "
            f"reason={decision.reason[:100]}..."
        )
        
        # TODO: Phase 5 (resolution - generate user message or review packet)
        
        workflow.logger.info(f"Completed complaint workflow: {workflow_id}")
        return WorkflowResult(
            complaint_id=workflow_id,
            terminal_status=TerminalStatus.COMPLETED,
            action=decision.action,
            reason=decision.reason
        )
