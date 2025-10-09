"""
Unit tests for complaint workflow using Temporal test environment.

These tests run in-memory (no Temporal server needed) and do not appear in UI.
They are fast and suitable for TDD during development.
"""

import uuid
import pytest
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

from workflow import ComplaintWorkflow
from activities import classify_complaint_activity
from models import ComplaintIn, TerminalStatus


@pytest.mark.asyncio
async def test_workflow_complaint() -> None:
    """
    Unit test: Verify workflow handles actual complaints correctly.
    
    Uses in-memory time-skipping environment (fast, no Temporal server needed).
    Workflows do NOT appear in Temporal UI.
    """
    # Generate unique task queue for this test
    task_queue_name = str(uuid.uuid4())
    
    # Use time-skipping test environment
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Create worker with the workflow and activities
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ComplaintWorkflow],
            activities=[classify_complaint_activity],
        ):
            # Sample complaint with simplified structure
            complaint = ComplaintIn(
                message="My order arrived broken! The jar was damaged.",
                user_id="test_user"
            )
            
            # Execute workflow
            result = await env.client.execute_workflow(
                ComplaintWorkflow.run,
                complaint,
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )
            
            # Verify result structure
            assert result.terminal_status == TerminalStatus.COMPLETED
            # Should be classified as complaint (LLM should detect "broken", "damaged")
            assert result.reason != "NOT_COMPLAINT"


@pytest.mark.asyncio
async def test_workflow_non_complaint() -> None:
    """
    Unit test: Verify workflow handles non-complaints correctly.
    
    Should classify as NOT_COMPLAINT and return appropriate user message.
    """
    task_queue_name = str(uuid.uuid4())
    
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue_name,
            workflows=[ComplaintWorkflow],
            activities=[classify_complaint_activity],
        ):
            # Sample non-complaint (order inquiry, no complaint keywords)
            complaint = ComplaintIn(
                message="Hello! Do you have organic tomatoes available for next week?",
                user_id="test_user"
            )
            
            # Execute workflow
            result = await env.client.execute_workflow(
                ComplaintWorkflow.run,
                complaint,
                id=str(uuid.uuid4()),
                task_queue=task_queue_name,
            )
            
            # Verify non-complaint handling
            assert result.terminal_status == TerminalStatus.COMPLETED
            assert result.reason == "NOT_COMPLAINT"
            assert result.user_message is not None
            assert "inquiry" in result.user_message.lower() or "question" in result.user_message.lower()
