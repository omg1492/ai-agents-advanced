"""
Ad-hoc test to verify when code_interpreter outputs are available.

Tests:
1. Streaming API - check if outputs appear in streaming events
2. Non-streaming API - check if outputs appear in full response
3. Retrieve after streaming - check if outputs appear in retrieved response

This will confirm the API behavior before implementing the workaround.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from openai import AsyncOpenAI

# Load environment from deploy/local/.env
env_path = Path(__file__).parent.parent.parent / "deploy" / "local" / ".env"
load_dotenv(env_path)

# Get configuration from unified env vars
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
api_version = os.getenv("OPENAI_API_VERSION", "preview")
deployment_name = os.getenv("OPENAI_MODEL")

if not api_key or not base_url or not deployment_name:
    print("❌ Missing required environment variables:")
    print(f"  OPENAI_API_KEY: {'✓' if api_key else '✗'}")
    print(f"  OPENAI_BASE_URL: {'✓' if base_url else '✗'}")
    print(f"  OPENAI_MODEL: {'✓' if deployment_name else '✗'}")
    sys.exit(1)

# Initialize client using the same pattern as OpenAIService
default_query = None
if base_url:
    default_query = {"api-version": api_version}

client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url,
    default_query=default_query
)

DEPLOYMENT_NAME = deployment_name

# Simple code that generates an image
CODE_REQUEST = "Create a simple bar chart with values [10, 20, 30, 40] and save it as a PNG file."


async def test_streaming():
    """Test 1: Check if outputs appear in streaming events."""
    print("=" * 80)
    print("TEST 1: STREAMING API - Check for outputs in events")
    print("=" * 80)

    try:
        response_stream = await client.responses.create(
            model=DEPLOYMENT_NAME,
            instructions="You are a helpful assistant. Execute code when asked.",
            input=[{"role": "user", "content": CODE_REQUEST}],
            tools=[{"type": "code_interpreter"}],
            stream=True,
        )

        response_id_from_stream = None
        code_interpreter_completed_events = []
        output_item_done_events = []
        
        print("\nStreaming events:")
        async for event in response_stream:
            event_type = event.type
            
            # Capture response ID
            if event_type == "response.created":
                response_id_from_stream = event.response.id
                print(f"  ✓ response.created: id={response_id_from_stream}")
            
            # Check code_interpreter events
            elif event_type == "response.code_interpreter_call.completed":
                code_interpreter_completed_events.append(event)
                print(f"  ✓ {event_type}: item_id={event.item_id}, output_index={event.output_index}")
                
                # Check if outputs field exists
                has_outputs = hasattr(event, 'outputs')
                outputs_value = getattr(event, 'outputs', None) if has_outputs else None
                print(f"    - Has 'outputs' attribute: {has_outputs}")
                print(f"    - outputs value: {outputs_value}")
                print(f"    - Available attributes: {[attr for attr in dir(event) if not attr.startswith('_')]}")
            
            # Check output_item.done events
            elif event_type == "response.output_item.done":
                item = event.item
                if item.type == "code_interpreter_call":
                    output_item_done_events.append(event)
                    print(f"  ✓ {event_type}: item_id={item.id}, type={item.type}")
                    
                    # Check if outputs field exists
                    has_outputs = hasattr(item, 'outputs')
                    outputs_value = getattr(item, 'outputs', None) if has_outputs else None
                    print(f"    - Has 'outputs' attribute: {has_outputs}")
                    print(f"    - outputs value: {outputs_value}")
                    print(f"    - Available attributes: {[attr for attr in dir(item) if not attr.startswith('_')]}")

        print("\n📊 Streaming Summary:")
        print(f"  - Response ID captured: {response_id_from_stream}")
        print(f"  - code_interpreter.completed events: {len(code_interpreter_completed_events)}")
        print(f"  - output_item.done (code_interpreter) events: {len(output_item_done_events)}")
        print("  - Any outputs in streaming events? NO" if not any(
            getattr(e, 'outputs', None) for e in code_interpreter_completed_events + 
            [e.item for e in output_item_done_events]
        ) else "  - Outputs found in streaming!")
        
        return response_id_from_stream

    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_retrieve(response_id):
    """Test 2: Retrieve full response and check for outputs."""
    print("\n" + "=" * 80)
    print("TEST 2: RETRIEVE FULL RESPONSE - Check for outputs")
    print("=" * 80)

    if not response_id:
        print("❌ No response ID from streaming test, cannot retrieve")
        return

    try:
        full_response = await client.responses.retrieve(response_id)
        
        print(f"\nRetrieved response: {full_response.id}")
        print(f"Status: {full_response.status}")
        print(f"Has 'output' attribute: {hasattr(full_response, 'output')}")
        
        if hasattr(full_response, 'output'):
            output_items = full_response.output
            print(f"Number of output items: {len(output_items)}")
            
            for idx, item in enumerate(output_items):
                print(f"\n  Output item {idx}:")
                print(f"    - Type: {item.type}")
                print(f"    - ID: {item.id}")
                
                if item.type == "code_interpreter_call":
                    has_outputs = hasattr(item, 'outputs')
                    print(f"    - Has 'outputs' attribute: {has_outputs}")
                    
                    if has_outputs:
                        outputs = item.outputs
                        print(f"    - outputs type: {type(outputs)}")
                        print(f"    - outputs value: {outputs}")
                        
                        if outputs:
                            print(f"    - Number of outputs: {len(outputs)}")
                            for output_idx, output in enumerate(outputs):
                                print(f"\n      Output {output_idx}:")
                                print(f"        - Type: {output.type}")
                                
                                if output.type == "image":
                                    print(f"        - URL: {getattr(output, 'url', 'N/A')}")
                                    print(f"        - Has 'file_id': {hasattr(output, 'file_id')}")
                                    if hasattr(output, 'file_id'):
                                        print(f"        - file_id: {output.file_id}")
                                    print(f"        - All attributes: {[attr for attr in dir(output) if not attr.startswith('_')]}")
                                elif output.type == "logs":
                                    logs = getattr(output, 'logs', '')
                                    print(f"        - Logs (first 200 chars): {logs[:200]}")
                        else:
                            print("    - ⚠️ outputs is empty or None")
                    else:
                        print("    - ⚠️ No 'outputs' attribute found")
                        print(f"    - Available attributes: {[attr for attr in dir(item) if not attr.startswith('_')]}")

        print("\n📊 Retrieve Summary:")
        if hasattr(full_response, 'output'):
            code_interp_items = [item for item in full_response.output if item.type == "code_interpreter_call"]
            print(f"  - code_interpreter_call items: {len(code_interp_items)}")
            
            items_with_outputs = [item for item in code_interp_items if hasattr(item, 'outputs') and item.outputs]
            print(f"  - Items with outputs: {len(items_with_outputs)}")
            
            if items_with_outputs:
                total_outputs = sum(len(item.outputs) for item in items_with_outputs)
                print(f"  - Total outputs found: {total_outputs}")
                print("  - ✅ OUTPUTS ARE AVAILABLE IN RETRIEVED RESPONSE")
            else:
                print("  - ❌ NO OUTPUTS FOUND IN RETRIEVED RESPONSE")
        else:
            print("  - ❌ No 'output' attribute in response")

    except Exception as e:
        print(f"❌ Retrieve test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_non_streaming():
    """Test 3: Check if outputs appear in non-streaming response."""
    print("\n" + "=" * 80)
    print("TEST 3: NON-STREAMING API - Check for outputs in direct response")
    print("=" * 80)

    try:
        direct_response = await client.responses.create(
            model=DEPLOYMENT_NAME,
            instructions="You are a helpful assistant. Execute code when asked.",
            input=[{"role": "user", "content": CODE_REQUEST}],
            tools=[{"type": "code_interpreter"}],
            stream=False,  # No streaming
        )
        
        print(f"\nDirect response: {direct_response.id}")
        print(f"Status: {direct_response.status}")
        print(f"Has 'output' attribute: {hasattr(direct_response, 'output')}")
        
        if hasattr(direct_response, 'output'):
            output_items = direct_response.output
            print(f"Number of output items: {len(output_items)}")
            
            code_interp_items = [item for item in output_items if item.type == "code_interpreter_call"]
            print(f"code_interpreter_call items: {len(code_interp_items)}")
            
            for item in code_interp_items:
                has_outputs = hasattr(item, 'outputs')
                print(f"\n  code_interpreter_call item {item.id}:")
                print(f"    - Has 'outputs' attribute: {has_outputs}")
                
                if has_outputs and item.outputs:
                    print(f"    - Number of outputs: {len(item.outputs)}")
                    for output in item.outputs:
                        print(f"      - Output type: {output.type}")
                        if output.type == "image":
                            print(f"        URL: {getattr(output, 'url', 'N/A')}")
                            print(f"        file_id: {getattr(output, 'file_id', 'N/A')}")

        print("\n📊 Non-streaming Summary:")
        if hasattr(direct_response, 'output'):
            code_interp_items = [item for item in direct_response.output if item.type == "code_interpreter_call"]
            items_with_outputs = [item for item in code_interp_items if hasattr(item, 'outputs') and item.outputs]
            
            if items_with_outputs:
                total_outputs = sum(len(item.outputs) for item in items_with_outputs)
                print(f"  - ✅ OUTPUTS AVAILABLE IN NON-STREAMING: {total_outputs} outputs")
            else:
                print("  - ❌ NO OUTPUTS IN NON-STREAMING")
        else:
            print("  - ❌ No 'output' attribute")

    except Exception as e:
        print(f"❌ Non-streaming test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    response_id = await test_streaming()
    if response_id:
        await test_retrieve(response_id)
    await test_non_streaming()
    
    print("\n" + "=" * 80)
    print("FINAL CONCLUSION")
    print("=" * 80)
    print("""
Expected behavior (based on Azure docs):
1. Streaming events: NO outputs (only text deltas and event notifications)
2. Retrieved response: YES outputs (full response object has outputs)
3. Non-streaming: YES outputs (full response object has outputs)

If tests confirm this, then our workaround (retrieve after streaming) is correct.
""")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
