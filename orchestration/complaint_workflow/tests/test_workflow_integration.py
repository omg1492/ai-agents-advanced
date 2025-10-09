"""
Integration test for complaint workflow.

This test runs against the actual Temporal dev server (localhost:7233)
and workflows will be visible in the Temporal UI at http://localhost:8233

Prerequisites:
- Temporal dev server must be running: temporal server start-dev
"""

import asyncio
import uuid
import pytest
from temporalio.client import Client
from temporalio.worker import Worker

from workflow import ComplaintWorkflow
from activities import classify_complaint_activity
from models import ComplaintIn, TerminalStatus
from worker import TASK_QUEUE_NAME


@pytest.mark.asyncio
async def test_workflow_against_temporal_server() -> None:
    """
    Integration test: Run workflow against real Temporal server.
    
    This test will appear in the Temporal UI at http://localhost:8233
    
    Skip this test if Temporal server is not running:
    pytest -v -k "not temporal_server"
    """
    # Connect to real Temporal server
    try:
        client = await Client.connect("localhost:7233", namespace="default")
    except Exception as e:
        pytest.skip(f"Temporal server not available: {e}")
    
    # Generate unique IDs for this test run
    test_run_id = str(uuid.uuid4())[:8]
    workflow_id = f"test-complaint-{test_run_id}"
    
    # Create test complaint with simplified structure
    complaint = ComplaintIn(
        message="My order arrived broken! The jar was damaged.",
        user_id=f"test_user_{test_run_id}"
    )
    
    # Start worker in background with activities
    worker = Worker(
        client,
        task_queue=TASK_QUEUE_NAME,
        workflows=[ComplaintWorkflow],
        activities=[classify_complaint_activity],
    )
    
    async def run_worker():
        """Run worker until task is complete."""
        await worker.run()
    
    # Start worker as background task
    worker_task = asyncio.create_task(run_worker())
    
    try:
        # Execute workflow against real server
        print(f"\n🚀 Starting workflow: {workflow_id}")
        print(f"   View in UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")
        
        result = await client.execute_workflow(
            ComplaintWorkflow.run,
            complaint,
            id=workflow_id,
            task_queue=TASK_QUEUE_NAME,
        )
        
        print(f"✅ Workflow completed: {result}")
        
        # Verify result structure
        assert result.terminal_status == TerminalStatus.COMPLETED
        assert result.user_message is not None
        
    finally:
        # Shutdown worker gracefully
        await worker.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    """
    Run this test directly to see workflow in Temporal UI:
    
    1. Start Temporal server:
       temporal server start-dev
       
    2. Run this test:
       uv run python tests/test_workflow_integration.py
       
    3. View in UI:
       http://localhost:8233
    """
    asyncio.run(test_workflow_against_temporal_server())
