"""
Client script to submit individual complaints to running workflow worker.

Usage:
    Terminal 1: uv run python worker.py
    Terminal 2: uv run python client_run.py complaints/complaint1.json

Prerequisites:
- Temporal server running (temporal server start-dev)
- Worker running (python worker.py)
- Azure OpenAI configured in .env
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from workflow import ComplaintWorkflow, TASK_QUEUE_NAME
from models import ComplaintIn

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def submit_complaint(complaint_file: str):
    """
    Load complaint from JSON file and submit to workflow.
    
    Args:
        complaint_file: Path to JSON file containing complaint data
    """
    # Load complaint
    try:
        with open(complaint_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        complaint = ComplaintIn(**data)
        logger.info(f"✅ Loaded complaint from {complaint_file}")
        logger.info(f"   User: {complaint.user_id}")
        logger.info(f"   Message: {complaint.message[:100]}...")
    except FileNotFoundError:
        logger.error(f"❌ File not found: {complaint_file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error loading {complaint_file}: {e}")
        sys.exit(1)
    
    # Connect to Temporal
    try:
        client = await Client.connect(
            "localhost:7233",
            namespace="default",
            data_converter=pydantic_data_converter
        )
        logger.info("✅ Connected to Temporal server")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Temporal server: {e}")
        logger.error("")
        logger.error("Make sure Temporal server is running:")
        logger.error("  temporal server start-dev")
        sys.exit(1)
    
    # Generate workflow ID from filename
    filename = Path(complaint_file).stem
    workflow_id = f"complaint-{filename}"
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"🚀 Submitting complaint to workflow")
    logger.info("=" * 80)
    logger.info(f"   Workflow ID: {workflow_id}")
    logger.info(f"   Task Queue: {TASK_QUEUE_NAME}")
    logger.info(f"   View in UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")
    logger.info("")
    
    try:
        # Execute workflow
        logger.info("📤 Sending to workflow...")
        result = await client.execute_workflow(
            ComplaintWorkflow.run,
            complaint,
            id=workflow_id,
            task_queue=TASK_QUEUE_NAME,
        )
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ WORKFLOW COMPLETED")
        logger.info("=" * 80)
        logger.info(f"   Status: {result.terminal_status}")
        if result.action:
            logger.info(f"   Action: {result.action}")
        if result.reason:
            logger.info(f"   Reason: {result.reason}")
        if result.user_message:
            logger.info("")
            logger.info("📧 User Message:")
            logger.info("-" * 80)
            logger.info(result.user_message)
            logger.info("-" * 80)
        if result.review_packet_id:
            logger.info(f"   Review Packet ID: {result.review_packet_id}")
        logger.info("")
        logger.info(f"🌐 View workflow details: http://localhost:8233/namespaces/default/workflows/{workflow_id}")
        logger.info("=" * 80)
        logger.info("")
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("❌ WORKFLOW EXECUTION FAILED")
        logger.error("=" * 80)
        logger.error(f"   Error: {e}")
        logger.error("")
        logger.error("Common issues:")
        logger.error("  - Worker not running (run: uv run python worker.py)")
        logger.error("  - Temporal server not running (run: temporal server start-dev)")
        logger.error("  - Azure OpenAI not configured (.env file)")
        logger.error("=" * 80)
        logger.error("")
        sys.exit(1)


async def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: uv run python client_run.py <complaint_json_file>")
        print("")
        print("Examples:")
        print("  uv run python client_run.py complaints/complaint1.json")
        print("  uv run python client_run.py complaints/complaint2.json")
        print("  uv run python client_run.py complaints/non-complaint.json")
        sys.exit(1)
    
    complaint_file = sys.argv[1]
    await submit_complaint(complaint_file)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Interrupted by user")
        sys.exit(0)
