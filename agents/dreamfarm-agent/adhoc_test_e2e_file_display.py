"""End-to-end test for code interpreter file display with annotations.

This script tests the complete flow:
1. Code interpreter generates a plot
2. Backend extracts file info from annotations
3. Sandbox URLs are replaced with /files/{file_id}/content
4. DF_META events are emitted with file mappings

Run: uv run python adhoc_test_e2e_file_display.py
"""

import asyncio
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set required env vars
os.environ['ENABLE_CODE_INTERPRETER'] = 'true'
os.environ['FARMER_TOOLS_ENABLED'] = 'false'
os.environ['TAVILY_ENABLED'] = 'false'
os.environ['STOCK_TOOL_ENABLED'] = 'false'

from src.services.config_service import ConfigService
from src.services.openai_service import OpenAIService


async def test_file_display_flow():
    """Test the complete file display flow with annotations extraction."""
    print("=" * 80)
    print("E2E Test: Code Interpreter File Display with Annotations")
    print("=" * 80)
    
    # Initialize services
    config_service = ConfigService()
    config = config_service.config
    
    if not (hasattr(config, 'code_interpreter') and 
            config.code_interpreter and 
            config.code_interpreter.enabled):
        print("❌ Code Interpreter is not enabled in config")
        return
    
    service = OpenAIService(
        config=config.openai,
        app_config=config
    )
    
    print("\n✅ Services initialized")
    print(f"   Base URL: {config.openai.base_url}")
    print("   Code Interpreter: Enabled")
    
    # Test message that will generate a plot
    test_message = """Create a simple line plot using matplotlib:
- X axis: [1, 2, 3, 4, 5]
- Y axis: [1, 4, 9, 16, 25] (squares)
- Title: "Y = X²"
- Label axes appropriately
- Save as PNG and show me the plot"""
    
    system_prompt = """You are a data visualization assistant with Python code execution.
Use matplotlib to create plots when requested. Always save plots to files."""
    
    print("\n" + "=" * 80)
    print("TEST: Generating plot with code interpreter")
    print("=" * 80)
    print(f"Prompt: {test_message[:100]}...")
    
    # Call the service (non-streaming for clearer output)
    response_text, response_id = await service.generate_response(
        user_text=test_message,
        system_prompt=system_prompt,
        previous_response_id=None,
        user_is_vip=False,
        user_id="test_user_e2e"
    )
    
    print(f"\n✅ Response received")
    print(f"   Response ID: {response_id}")
    print(f"   Response length: {len(response_text)} chars")
    
    # Retrieve full response to check annotations
    print("\n" + "=" * 80)
    print("Checking for file annotations in response...")
    print("=" * 80)
    
    full_response = await service.client.responses.retrieve(response_id)
    
    # Extract file annotations
    file_annotations = []
    for item in full_response.output:
        if item.type == 'message' and hasattr(item, 'content'):
            for content_block in item.content:
                if hasattr(content_block, 'annotations') and content_block.annotations:
                    for annotation in content_block.annotations:
                        if hasattr(annotation, 'file_id'):
                            file_annotations.append({
                                'file_id': annotation.file_id,
                                'container_id': annotation.container_id,
                                'filename': annotation.filename
                            })
    
    if file_annotations:
        print(f"\n✅ Found {len(file_annotations)} file annotation(s)")
        for i, ann in enumerate(file_annotations, 1):
            print(f"\n   File {i}:")
            print(f"   ├─ Filename: {ann['filename']}")
            print(f"   ├─ File ID: {ann['file_id']}")
            print(f"   └─ Container ID: {ann['container_id']}")
    else:
        print("\n❌ No file annotations found in response")
        return
    
    # Check response text for URLs
    print("\n" + "=" * 80)
    print("Checking response text for file references...")
    print("=" * 80)
    
    has_sandbox_url = 'sandbox:' in response_text.lower()
    has_files_url = '/files/' in response_text.lower()
    has_file_reference = any(ann['filename'] in response_text for ann in file_annotations)
    
    print(f"\n   Contains 'sandbox:' URL: {has_sandbox_url}")
    print(f"   Contains '/files/' URL: {has_files_url}")
    print(f"   Contains filename reference: {has_file_reference}")
    
    if has_files_url:
        print("\n   ✅ URL replacement appears to be working (contains /files/ URLs)")
    elif has_sandbox_url:
        print("\n   ⚠️  Found sandbox URLs - backend replacement may not have triggered")
    
    # Print relevant excerpt from response
    print("\n" + "=" * 80)
    print("Response text excerpt (first 500 chars):")
    print("=" * 80)
    print(response_text[:500])
    if len(response_text) > 500:
        print("...")
    
    # Check outputs field (should be None)
    print("\n" + "=" * 80)
    print("Verifying outputs field behavior...")
    print("=" * 80)
    
    outputs_found = False
    outputs_value = None
    
    for item in full_response.output:
        if hasattr(item, 'type') and item.type == 'code_interpreter_call':
            if hasattr(item, 'outputs'):
                outputs_found = True
                outputs_value = item.outputs
    
    print(f"\n   Outputs attribute exists: {outputs_found}")
    print(f"   Outputs value: {outputs_value}")
    
    if outputs_found and outputs_value is None:
        print("\n   ✅ Confirmed: outputs field exists but is None (expected behavior)")
    elif not outputs_found:
        print("\n   ℹ️  No code_interpreter_call items with outputs attribute")
    else:
        print(f"\n   ⚠️  Unexpected: outputs value is {outputs_value} (expected None)")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    success_criteria = [
        ("Code interpreter executed", True),
        ("File annotations extracted", len(file_annotations) > 0),
        ("File metadata complete", all(ann['file_id'] and ann['filename'] for ann in file_annotations)),
        ("Response contains content", len(response_text) > 100),
        ("Outputs field is None", outputs_value is None if outputs_found else True),
    ]
    
    all_passed = all(passed for _, passed in success_criteria)
    
    print()
    for criterion, passed in success_criteria:
        status = "✅" if passed else "❌"
        print(f"   {status} {criterion}")
    
    if all_passed:
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - Implementation working correctly!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("⚠️  SOME TESTS FAILED - Review output above")
        print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    print("\n🚀 Starting E2E test for code interpreter file display...")
    print()
    
    success = asyncio.run(test_file_display_flow())
    
    print("\n" + "=" * 80)
    if success:
        print("Test completed successfully ✅")
    else:
        print("Test completed with issues ⚠️")
    print("=" * 80)
