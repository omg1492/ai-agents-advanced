"""Worker process for complaint handling."""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter

# Load environment variables before importing workflows/activities
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import the workflow using the sandbox passthrough pattern
with workflow.unsafe.imports_passed_through():
    from workflow import ComplaintWorkflow
    from activities import (
        classify_complaint_activity,
        extract_complaint_info_activity,
        fetch_user_profile_activity,
        decide_complaint_validity_activity
    )


# Task queue name - shared constant
TASK_QUEUE_NAME = "complaint-workflow-queue"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Start the Worker to process complaint workflows.
    
    The Worker connects to the Temporal server and polls the task queue
    for workflows and activities to execute.
    """
    # Connect to local Temporal server with Pydantic v2 data converter
    client = await Client.connect(
        "localhost:7233",
        namespace="default",
        data_converter=pydantic_data_converter
    )
    
    logger.info("Connected to Temporal server")
    
    # Create worker that listens to the task queue
    worker = Worker(
        client,
        task_queue=TASK_QUEUE_NAME,
        workflows=[ComplaintWorkflow],
        activities=[
            classify_complaint_activity,
            extract_complaint_info_activity,
            fetch_user_profile_activity,
            decide_complaint_validity_activity
        ],
    )
    
    logger.info(f"Worker started, listening on task queue: {TASK_QUEUE_NAME}")
    logger.info("Registered workflows: ComplaintWorkflow")
    logger.info("Registered activities: classify_complaint, extract_complaint_info, fetch_user_profile, decide_complaint_validity")
    
    # Run the worker (blocks until interrupted)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
