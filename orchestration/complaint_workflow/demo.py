"""
Interactive demo for complaint workflow.

Loads complaint JSON files and processes them through the workflow with detailed logging.
Shows classification results and workflow execution in real-time.

This demo automatically starts its own worker and shuts it down when finished.

Prerequisites: 
- Temporal server running (temporal server start-dev)
- Azure OpenAI configured in .env
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

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
    from activities import classify_complaint_activity
    from models import ComplaintIn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def load_complaint(file_path: str) -> Optional[ComplaintIn]:
    """Load complaint from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        complaint = ComplaintIn(**data)
        logger.info(f"✅ Loaded complaint from {file_path}")
        logger.info(f"   User: {complaint.user_id}")
        logger.info(f"   Message: {complaint.message[:100]}...")
        return complaint
    except FileNotFoundError:
        logger.error(f"❌ File not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"❌ Error loading {file_path}: {e}")
        return None


async def process_complaint(client: Client, complaint: ComplaintIn, name: str):
    """Process a single complaint through the workflow."""
    logger.info("=" * 80)
    logger.info(f"🚀 Processing: {name}")
    logger.info("=" * 80)
    
    # Generate workflow ID
    workflow_id = f"complaint-demo-{name.replace('.json', '')}"
    
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
        logger.info("✅ Workflow completed!")
        logger.info(f"   Status: {result.terminal_status}")
        if result.action:
            logger.info(f"   Action: {result.action}")
        if result.reason:
            logger.info(f"   Reason: {result.reason}")
        if result.user_message:
            logger.info(f"   User Message: {result.user_message}")
        
    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {e}")
        logger.error("   Common issues:")
        logger.error("     - Temporal server not running (run: temporal server start-dev)")
        logger.error("     - Azure OpenAI not configured (.env file)")
        logger.error("     - Check worker logs above for errors")
    
    logger.info("")


async def main():
    """Run demo with all example complaints, managing its own worker."""
    print("\n" + "=" * 80)
    print("COMPLAINT WORKFLOW DEMO - Step 1 & 2 Implementation")
    print("=" * 80)
    print()
    print("This demo processes example complaints through:")
    print("  ✓ Step 1: Load complaint from JSON file")
    print("  ✓ Step 2: LLM classification (is it a complaint?)")
    print()
    print("=" * 80)
    print()
    
    # Check prerequisites
    logger.info("📋 Checking prerequisites...")
    
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
        return
    
    # Start worker in background
    logger.info("🔧 Starting worker...")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE_NAME,
        workflows=[ComplaintWorkflow],
        activities=[classify_complaint_activity]
    )
    
    # Run worker as background task
    async def run_worker():
        """Run worker until shutdown."""
        await worker.run()
    
    worker_task = asyncio.create_task(run_worker())
    logger.info(f"✅ Worker started on task queue: {TASK_QUEUE_NAME}")
    logger.info("")
    
    # Small delay to ensure worker is ready
    await asyncio.sleep(0.5)
    
    try:
        # Process each example complaint
        complaints_dir = Path(__file__).parent / "complaints"
        complaint_files = [
            ("complaint1.json", "Valid Complaint"),
            ("non-complaint.json", "Non-Complaint (Inquiry)"),
        ]
        
        for filename, description in complaint_files:
            file_path = complaints_dir / filename
            
            # Load complaint
            complaint = await load_complaint(str(file_path))
            if not complaint:
                continue
            
            logger.info(f"   Description: {description}")
            logger.info("")
            
            # Process through workflow
            await process_complaint(client, complaint, filename)
            
            # Small delay between complaints
            await asyncio.sleep(1)
        
        # Summary
        print()
        print("=" * 80)
        print("DEMO COMPLETE")
        print("=" * 80)
        print()
        print("🌐 View all workflows in Temporal UI:")
        print("   http://localhost:8233")
        print()
        print("📊 Check the logs above to see:")
        print("   • Complaint classification results")
        print("   • Confidence scores")
        print("   • Workflow decisions")
        print()
        print("=" * 80)
        print()
    
    finally:
        # Shutdown worker gracefully
        logger.info("🛑 Shutting down worker...")
        await worker.shutdown()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ Worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Demo interrupted by user")
        sys.exit(0)
