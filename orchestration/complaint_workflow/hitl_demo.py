"""
Human-in-the-Loop (HITL) Demo for complaint workflow.

Demonstrates Temporal signals, queries, and wait_condition patterns:
1. Submits a complaint that triggers HUMAN_REVIEW
2. Queries workflow status while waiting
3. Sends approval signal to continue workflow
4. Shows final result after human decision

Prerequisites:
- Temporal server running (temporal server start-dev)
- OpenAI configured in .env
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from temporalio import workflow
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

# Load environment variables
load_dotenv()

# Import workflows and activities using sandbox passthrough
with workflow.unsafe.imports_passed_through():
    from workflow import ComplaintWorkflow, TASK_QUEUE_NAME
    from activities import (
        classify_complaint_activity,
        extract_complaint_info_activity,
        fetch_user_profile_activity,
        decide_complaint_validity_activity,
        generate_user_message_activity,
        generate_review_packet_activity,
        notify_reviewer_activity,
        generate_human_decision_message_activity,
    )
    from models import ComplaintIn, HumanDecision, HumanReviewInput

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def load_complaint(file_path: str) -> ComplaintIn | None:
    """Load complaint from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ComplaintIn(**data)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


async def run_hitl_demo(client: Client, complaint: ComplaintIn, workflow_id: str):
    """
    Run the HITL demo:
    1. Start workflow (non-blocking)
    2. Query status after 2 seconds
    3. Send approval signal after 5 seconds
    4. Wait for final result
    """
    print("\n" + "=" * 80)
    print("PHASE 1: Starting Workflow")
    print("=" * 80)

    # Start workflow (non-blocking)
    handle = await client.start_workflow(
        ComplaintWorkflow.run,
        complaint,
        id=workflow_id,
        task_queue=TASK_QUEUE_NAME,
    )

    logger.info(f"Workflow started: {workflow_id}")
    logger.info(f"View in UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")
    print()

    # Wait for workflow to reach AWAITING_HUMAN_REVIEW phase
    print("=" * 80)
    print("PHASE 2: Waiting for workflow to reach AWAITING_HUMAN_REVIEW...")
    print("=" * 80)

    # Poll status until AWAITING_HUMAN_REVIEW or timeout
    max_wait = 60  # seconds
    poll_interval = 2  # seconds
    elapsed = 0

    while elapsed < max_wait:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        try:
            status = await handle.query(ComplaintWorkflow.get_status)
            logger.info(f"Current phase: {status['phase']}")

            if status['phase'] == 'AWAITING_HUMAN_REVIEW':
                logger.info("Workflow is now waiting for human decision!")
                print()

                # Display review packet
                if status['review_packet']:
                    print("=" * 80)
                    print("REVIEW PACKET (for human reviewer)")
                    print("=" * 80)
                    rp = status['review_packet']
                    print(f"Summary: {rp['summary']}")
                    print(f"Priority: {rp['priority']}")
                    print(f"Recommendation: {rp['recommended_action']}")
                    print()
                    print("Arguments FOR approval:")
                    for arg in rp['arguments_for_approval']:
                        print(f"  + {arg}")
                    print()
                    print("Arguments AGAINST approval:")
                    for arg in rp['arguments_against_approval']:
                        print(f"  - {arg}")
                    print()
                break

            if status['phase'] == 'COMPLETED':
                # Workflow completed without HUMAN_REVIEW (e.g., VALID or NOT_VALID)
                logger.info("Workflow completed without HUMAN_REVIEW")
                result = await handle.result()
                return result

        except Exception as e:
            logger.warning(f"Query failed (workflow may still be processing): {e}")

    # Phase 3: Send human decision signal
    print("=" * 80)
    print("PHASE 3: Simulating Human Decision")
    print("=" * 80)
    print("Waiting 3 seconds before sending approval signal...")
    print("(In production, this would be a human reviewing the case)")
    print()

    await asyncio.sleep(3)

    # Send APPROVED signal
    decision = HumanReviewInput(
        decision=HumanDecision.APPROVED,
        reviewer_id="demo-reviewer-001",
        reviewer_notes="Verified customer claim. Photos confirm damage. Approving refund."
    )

    logger.info(f"Sending signal: {decision.decision.value}")
    logger.info(f"Reviewer: {decision.reviewer_id}")
    logger.info(f"Notes: {decision.reviewer_notes}")

    await handle.signal(ComplaintWorkflow.submit_human_decision, decision)
    logger.info("Signal sent successfully!")
    print()

    # Phase 4: Wait for final result
    print("=" * 80)
    print("PHASE 4: Waiting for Final Result")
    print("=" * 80)

    try:
        result = await handle.result()

        print()
        print("=" * 80)
        print("WORKFLOW COMPLETED")
        print("=" * 80)
        print(f"Terminal Status: {result.terminal_status}")
        print(f"Action: {result.action}")
        print(f"Reviewer ID: {result.reviewer_id}")
        print(f"Reviewer Notes: {result.reviewer_notes}")
        print()
        print("User Message:")
        print("-" * 40)
        print(result.user_message)
        print("-" * 40)

        return result

    except Exception as e:
        logger.error(f"Failed to get workflow result: {e}")
        return None


async def main():
    """Run HITL demo."""
    print("\n" + "=" * 80)
    print("HUMAN-IN-THE-LOOP (HITL) DEMO")
    print("=" * 80)
    print()
    print("This demo shows Temporal's signal/query patterns for human approval:")
    print("  1. Submit complaint that triggers HUMAN_REVIEW")
    print("  2. Workflow pauses at wait_condition")
    print("  3. Query workflow status (see review packet)")
    print("  4. Send approval signal")
    print("  5. Workflow continues and completes")
    print()
    print("=" * 80)
    print()

    # Connect to Temporal
    try:
        client = await Client.connect(
            "localhost:7233",
            namespace="default",
            data_converter=pydantic_data_converter
        )
        logger.info("Connected to Temporal server")
    except Exception as e:
        logger.error(f"Failed to connect to Temporal server: {e}")
        logger.error("Make sure Temporal server is running: temporal server start-dev")
        return

    # Start worker in background
    logger.info("Starting worker...")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE_NAME,
        workflows=[ComplaintWorkflow],
        activities=[
            classify_complaint_activity,
            extract_complaint_info_activity,
            fetch_user_profile_activity,
            decide_complaint_validity_activity,
            generate_user_message_activity,
            generate_review_packet_activity,
            notify_reviewer_activity,
            generate_human_decision_message_activity,
        ]
    )

    async def run_worker():
        await worker.run()

    worker_task = asyncio.create_task(run_worker())
    logger.info(f"Worker started on task queue: {TASK_QUEUE_NAME}")
    print()

    # Small delay for worker to be ready
    await asyncio.sleep(0.5)

    try:
        # Load complaint that triggers HUMAN_REVIEW
        # complaint2.json has suspicious profile that triggers human review
        complaints_dir = Path(__file__).parent / "complaints"
        complaint = await load_complaint(str(complaints_dir / "complaint2.json"))

        if not complaint:
            logger.error("Failed to load complaint file")
            return

        logger.info(f"Loaded complaint from user: {complaint.user_id}")
        logger.info(f"Message preview: {complaint.message[:100]}...")
        print()

        # Run HITL demo
        workflow_id = "hitl-demo-complaint2"
        await run_hitl_demo(client, complaint, workflow_id)

        # Summary
        print()
        print("=" * 80)
        print("HITL DEMO COMPLETE")
        print("=" * 80)
        print()
        print("Key Temporal patterns demonstrated:")
        print("  - workflow.signal: Received human decision externally")
        print("  - workflow.query: Read workflow state without mutation")
        print("  - workflow.wait_condition: Paused until signal received")
        print()
        print("View workflow history in Temporal UI:")
        print(f"  http://localhost:8233/namespaces/default/workflows/{workflow_id}")
        print()
        print("=" * 80)

    finally:
        # Shutdown worker
        logger.info("Shutting down worker...")
        await worker.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\nDemo interrupted by user")
        sys.exit(0)
