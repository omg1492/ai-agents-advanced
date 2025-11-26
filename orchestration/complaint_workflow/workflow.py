"""
Temporal workflow for complaint handling.

Orchestrates classification, field validation, data fetching, decision-making,
and resolution activities. Maintains determinism by delegating side-effects to activities.

Human-in-the-Loop (HITL) Extension:
- Signal handler for human decisions
- Query handler for workflow status
- wait_condition for pausing until human responds
- Timeout mechanism for auto-escalation
"""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow

from activities import (
    classify_complaint_activity,
    extract_complaint_info_activity,
    fetch_user_profile_activity,
    decide_complaint_validity_activity,
    generate_user_message_activity,
    generate_review_packet_activity,
    notify_reviewer_activity,
    generate_human_decision_message_activity,
    ACTIVITY_TIMEOUT,
    ACTIVITY_RETRY_POLICY
)
from models import (
    ComplaintIn,
    TerminalStatus,
    WorkflowResult,
    Action,
    HumanDecision,
    HumanReviewInput,
    ReviewPacket,
)

# Task queue constant (shared with worker)
TASK_QUEUE_NAME = "complaint-workflow-queue"

# Human review timeout (configurable via env in production)
HUMAN_REVIEW_TIMEOUT = timedelta(hours=24)  # 24h for testing; reduce in production


@workflow.defn
class ComplaintWorkflow:
    """
    Durable complaint handling workflow with Human-in-the-Loop support.

    Phases:
    1. Classification (is_complaint?)
    2. Field sufficiency check (has required identifiers?)
    3. Data fetch (order + user profile)
    4. Decision (VALID / NOT_VALID / HUMAN_REVIEW)
    5. Resolution (user message or review packet)
    6. [HITL] Wait for human decision (if HUMAN_REVIEW)
    7. [HITL] Process human decision and generate response
    """

    def __init__(self) -> None:
        """Initialize workflow state for HITL support."""
        self._human_decision: Optional[HumanReviewInput] = None
        self._review_packet: Optional[ReviewPacket] = None
        self._current_phase: str = "INIT"

    @workflow.signal
    def submit_human_decision(self, decision_input: HumanReviewInput) -> None:
        """
        Signal handler for human reviewer decision.

        Called externally (via CLI, API, or UI) to submit human decision.
        This unblocks the workflow waiting at wait_condition.
        """
        workflow.logger.info(
            f"Received human decision signal: decision={decision_input.decision}, "
            f"reviewer={decision_input.reviewer_id}"
        )
        self._human_decision = decision_input

    @workflow.query
    def get_status(self) -> dict:
        """
        Query handler for workflow status.

        Returns current phase and HITL state. Read-only, cannot mutate state.
        """
        return {
            "phase": self._current_phase,
            "awaiting_human": self._human_decision is None and self._review_packet is not None,
            "review_packet": self._review_packet.model_dump() if self._review_packet else None,
            "human_decision": self._human_decision.model_dump() if self._human_decision else None,
        }

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
        self._current_phase = "STARTED"

        workflow.logger.info(
            f"Starting complaint workflow: {workflow_id}, "
            f"user={complaint.user_id}, "
            f"message_len={len(complaint.message)}"
        )

        # Phase 1: Classify complaint
        self._current_phase = "CLASSIFYING"
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
        self._current_phase = "EXTRACTING"
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
        self._current_phase = "FETCHING_PROFILE"
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
        self._current_phase = "DECIDING"
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
        
        # Phase 5: Generate resolution (user message or review packet)
        self._current_phase = "GENERATING_RESOLUTION"

        if decision.action == Action.VALID or decision.action == Action.NOT_VALID:
            # Generate user-facing message
            user_message_obj = await workflow.execute_activity(
                generate_user_message_activity,
                args=[decision, extraction, user_profile],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=ACTIVITY_RETRY_POLICY
            )

            workflow.logger.info(
                f"Generated user message: {workflow_id}, "
                f"tone={user_message_obj.tone}, subject={user_message_obj.subject}"
            )

            self._current_phase = "COMPLETED"
            workflow.logger.info(f"Completed complaint workflow: {workflow_id}")
            return WorkflowResult(
                complaint_id=workflow_id,
                terminal_status=TerminalStatus.COMPLETED,
                action=decision.action,
                reason=decision.reason,
                user_message=user_message_obj.message
            )

        # HUMAN_REVIEW branch with HITL support
        # Phase 5b: Generate review packet for human evaluator
        self._review_packet = await workflow.execute_activity(
            generate_review_packet_activity,
            args=[decision, extraction, user_profile],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )

        workflow.logger.info(
            f"Generated review packet: {workflow_id}, "
            f"priority={self._review_packet.priority}"
        )

        # Phase 6: Notify reviewer (mock - just logs)
        self._current_phase = "NOTIFYING_REVIEWER"
        await workflow.execute_activity(
            notify_reviewer_activity,
            args=[self._review_packet, workflow_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )

        # Phase 7: Wait for human decision (with timeout)
        self._current_phase = "AWAITING_HUMAN_REVIEW"
        workflow.logger.info(
            f"Waiting for human decision: {workflow_id}, "
            f"timeout={HUMAN_REVIEW_TIMEOUT.total_seconds()}s"
        )

        # Use Temporal's wait_condition with asyncio timeout
        try:
            # workflow.wait_condition returns when lambda becomes True
            await asyncio.wait_for(
                workflow.wait_condition(lambda: self._human_decision is not None),
                timeout=HUMAN_REVIEW_TIMEOUT.total_seconds()
            )
        except asyncio.TimeoutError:
            workflow.logger.warning(
                f"Human review timeout: {workflow_id}, auto-escalating"
            )
            self._human_decision = HumanReviewInput(
                decision=HumanDecision.TIMEOUT_ESCALATED,
                reviewer_id="SYSTEM",
                reviewer_notes="Auto-escalated due to human review timeout"
            )

        # Phase 8: Process human decision
        self._current_phase = "PROCESSING_HUMAN_DECISION"
        workflow.logger.info(
            f"Processing human decision: {workflow_id}, "
            f"decision={self._human_decision.decision}, "
            f"reviewer={self._human_decision.reviewer_id}"
        )

        # Generate appropriate message based on human decision
        user_message_obj = await workflow.execute_activity(
            generate_human_decision_message_activity,
            args=[self._human_decision, extraction, user_profile],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY
        )

        # Map human decision to terminal status
        if self._human_decision.decision == HumanDecision.APPROVED:
            terminal_status = TerminalStatus.HUMAN_APPROVED
        elif self._human_decision.decision == HumanDecision.REJECTED:
            terminal_status = TerminalStatus.HUMAN_REJECTED
        else:  # TIMEOUT_ESCALATED
            terminal_status = TerminalStatus.TIMEOUT_ESCALATED

        self._current_phase = "COMPLETED"
        workflow.logger.info(
            f"Completed complaint workflow (HITL): {workflow_id}, "
            f"terminal_status={terminal_status}"
        )

        return WorkflowResult(
            complaint_id=workflow_id,
            terminal_status=terminal_status,
            action=decision.action,
            reason=decision.reason,
            user_message=user_message_obj.message,
            review_packet_id=f"review-{workflow_id}",
            reviewer_id=self._human_decision.reviewer_id,
            reviewer_notes=self._human_decision.reviewer_notes
        )
