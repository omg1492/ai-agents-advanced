"""
Human-in-the-Loop CLI Client for complaint workflow.

Provides commands to interact with running workflows:
- query: Check workflow status and review packet
- approve: Send approval signal
- reject: Send rejection signal

Usage:
    uv run python client_hitl.py query <workflow-id>
    uv run python client_hitl.py approve <workflow-id> --reviewer <id> [--notes "..."]
    uv run python client_hitl.py reject <workflow-id> --reviewer <id> [--notes "..."]

Prerequisites:
- Temporal server running (temporal server start-dev)
- Worker running (uv run python worker.py)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from temporalio import workflow
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import models using sandbox passthrough
with workflow.unsafe.imports_passed_through():
    from workflow import ComplaintWorkflow
    from models import HumanDecision, HumanReviewInput

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def query_workflow(client: Client, workflow_id: str) -> None:
    """Query workflow status and display review packet if available."""
    try:
        handle = client.get_workflow_handle(workflow_id)
        status = await handle.query(ComplaintWorkflow.get_status)

        print()
        print("=" * 60)
        print(f"WORKFLOW STATUS: {workflow_id}")
        print("=" * 60)
        print(f"Phase: {status['phase']}")
        print(f"Awaiting Human Decision: {status['awaiting_human']}")
        print()

        if status['review_packet']:
            print("REVIEW PACKET:")
            print("-" * 40)
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
            print(f"Customer Context: {rp['customer_context']}")
            print("-" * 40)

        if status['human_decision']:
            print()
            print("HUMAN DECISION (already received):")
            hd = status['human_decision']
            print(f"  Decision: {hd['decision']}")
            print(f"  Reviewer: {hd['reviewer_id']}")
            print(f"  Notes: {hd.get('reviewer_notes', 'None')}")

        print()
        print("=" * 60)

        if status['awaiting_human']:
            print()
            print("To approve this complaint:")
            print(f"  uv run python client_hitl.py approve {workflow_id} --reviewer YOUR_ID")
            print()
            print("To reject this complaint:")
            print(f"  uv run python client_hitl.py reject {workflow_id} --reviewer YOUR_ID --notes \"Reason\"")
            print()

    except Exception as e:
        logger.error(f"Failed to query workflow: {e}")
        logger.error("Make sure:")
        logger.error("  - Workflow exists and is running")
        logger.error("  - Worker is running (uv run python worker.py)")
        sys.exit(1)


async def send_decision(
    client: Client,
    workflow_id: str,
    decision: HumanDecision,
    reviewer_id: str,
    notes: str | None
) -> None:
    """Send human decision signal to workflow."""
    try:
        handle = client.get_workflow_handle(workflow_id)

        # First check if workflow is awaiting human decision
        try:
            status = await handle.query(ComplaintWorkflow.get_status)
            if not status['awaiting_human']:
                logger.warning(f"Workflow is not awaiting human decision (phase: {status['phase']})")
                if status['human_decision']:
                    logger.warning("A decision has already been submitted")
                    sys.exit(1)
        except Exception:
            # Query might fail if workflow is already completed, proceed with signal anyway
            pass

        # Create decision input
        decision_input = HumanReviewInput(
            decision=decision,
            reviewer_id=reviewer_id,
            reviewer_notes=notes
        )

        # Send signal
        await handle.signal(ComplaintWorkflow.submit_human_decision, decision_input)

        print()
        print("=" * 60)
        print("DECISION SENT SUCCESSFULLY")
        print("=" * 60)
        print(f"Workflow: {workflow_id}")
        print(f"Decision: {decision.value}")
        print(f"Reviewer: {reviewer_id}")
        if notes:
            print(f"Notes: {notes}")
        print()
        print("The workflow will now continue processing.")
        print(f"View in UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Failed to send decision: {e}")
        logger.error("Make sure:")
        logger.error("  - Workflow exists")
        logger.error("  - Temporal server is running")
        sys.exit(1)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Human-in-the-Loop CLI for complaint workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Query workflow status:
    uv run python client_hitl.py query complaint-demo-complaint2

  Approve a complaint:
    uv run python client_hitl.py approve complaint-demo-complaint2 --reviewer operator-1

  Reject a complaint with notes:
    uv run python client_hitl.py reject complaint-demo-complaint2 --reviewer operator-1 --notes "Insufficient evidence"
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Query command
    query_parser = subparsers.add_parser("query", help="Query workflow status")
    query_parser.add_argument("workflow_id", help="Workflow ID to query")

    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve the complaint")
    approve_parser.add_argument("workflow_id", help="Workflow ID to approve")
    approve_parser.add_argument("--reviewer", required=True, help="Reviewer ID")
    approve_parser.add_argument("--notes", default=None, help="Optional reviewer notes")

    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject the complaint")
    reject_parser.add_argument("workflow_id", help="Workflow ID to reject")
    reject_parser.add_argument("--reviewer", required=True, help="Reviewer ID")
    reject_parser.add_argument("--notes", default=None, help="Optional rejection reason")

    args = parser.parse_args()

    # Connect to Temporal
    try:
        client = await Client.connect(
            "localhost:7233",
            namespace="default",
            data_converter=pydantic_data_converter
        )
    except Exception as e:
        logger.error(f"Failed to connect to Temporal server: {e}")
        logger.error("Make sure Temporal server is running: temporal server start-dev")
        sys.exit(1)

    # Execute command
    if args.command == "query":
        await query_workflow(client, args.workflow_id)
    elif args.command == "approve":
        await send_decision(
            client,
            args.workflow_id,
            HumanDecision.APPROVED,
            args.reviewer,
            args.notes
        )
    elif args.command == "reject":
        await send_decision(
            client,
            args.workflow_id,
            HumanDecision.REJECTED,
            args.reviewer,
            args.notes
        )


if __name__ == "__main__":
    asyncio.run(main())
