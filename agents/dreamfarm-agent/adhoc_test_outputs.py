"""
Ad-hoc test to verify when code_interpreter outputs are available.
Tests both streaming and non-streaming Responses API calls.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from services.openai_service import OpenAIService

# Load environment from deploy/local/.env
env_path = Path(__file__).parent.parent.parent / "deploy" / "local" / ".env"
load_dotenv(env_path)

async def test_streaming_vs_nonstreaming():
    """Test if code_interpreter outputs are available in streaming vs non-streaming."""
    
    print("=" * 80)
    print("CODE INTERPRETER OUTPUTS TEST")
    print("=" * 80)
    print()
    
    # Initialize service (it will load config internally)
    openai_service = OpenAIService()
    
    # Get properly configured tools (includes code_interpreter with container)
    tools = openai_service.get_tools()
    
    # Code interpreter request that GENERATES AN IMAGE
    request_input = [
        {
            "role": "user",
            "content": "Generate a simple plot using matplotlib. Create a bar chart showing sales data: Product A=100, Product B=150, Product C=120. Save it as sales_chart.png."
        }
    ]
    
    # Test 1: NON-STREAMING (Full Response)
    print("TEST 1: NON-STREAMING Response")
    print("-" * 80)
    
    try:
        response = await openai_service.client.responses.create(
            model=openai_service.model_name,
            input=request_input,
            tools=tools,
            stream=False
        )
        
        print("[OK] Response received")
        print(f"  Response ID: {response.id}")
        print(f"  Status: {response.status}")
        print(f"  Output items: {len(response.output) if hasattr(response, 'output') else 'N/A'}")
        print()
        
        # Check for code_interpreter_call outputs
        if hasattr(response, 'output'):
            for i, item in enumerate(response.output):
                print(f"  Output item {i}:")
                print(f"    Type: {item.type}")
                
                if item.type == 'code_interpreter_call':
                    outputs = getattr(item, 'outputs', None)
                    print(f"    Has 'outputs' attribute: {outputs is not None}")
                    
                    # Debug: print ALL attributes
                    print(f"    Available attributes: {[a for a in dir(item) if not a.startswith('_')]}")
                    print(f"    Item dict: {item.__dict__ if hasattr(item, '__dict__') else 'N/A'}")
                    
                    if outputs:
                        print(f"    Number of outputs: {len(outputs)}")
                        for j, output in enumerate(outputs):
                            print(f"      Output {j}: type={output.type}")
                            if hasattr(output, 'file_id'):
                                print(f"        file_id: {output.file_id}")
                            if hasattr(output, 'url'):
                                print(f"        url: {output.url}")
                    else:
                        print("    [ERROR] outputs is None or missing!")
        print()
        
    except Exception as e:
        print(f"[ERROR] Non-streaming test failed: {e}")
        print()
    
    # Test 2: STREAMING Response
    print("TEST 2: STREAMING Response")
    print("-" * 80)
    
    try:
        stream = await openai_service.client.responses.create(
            model=openai_service.model_name,
            input=request_input,
            tools=tools,
            stream=True
        )
        
        print("[OK] Stream started")
        
        response_id = None
        event_count = 0
        code_interpreter_events = []
        
        async for event in stream:
            event_count += 1
            event_type = event.type
            
            # Capture response ID
            if event_type == "response.created":
                response_id = event.response.id
                print(f"  Response ID: {response_id}")
            
            # Track code_interpreter events
            if "code_interpreter" in event_type:
                code_interpreter_events.append(event)
                print(f"  Event: {event_type}")
                
                # Check for outputs attribute in completed event
                if event_type == "response.code_interpreter_call.completed":
                    has_outputs = hasattr(event, 'outputs')
                    print(f"    Has 'outputs' attribute: {has_outputs}")
                    if has_outputs:
                        outputs = event.outputs
                        print(f"    outputs value: {outputs}")
                
                # Check output_item.done events
                if event_type == "response.output_item.done":
                    item = event.item
                    print(f"    Item type: {item.type}")
                    if item.type == "code_interpreter_call":
                        has_outputs = hasattr(item, 'outputs')
                        print(f"    Item has 'outputs' attribute: {has_outputs}")
                        if has_outputs:
                            outputs = item.outputs
                            print(f"    Item outputs value: {outputs}")
        
        print("\n[OK] Stream completed")
        print(f"  Total events: {event_count}")
        print(  f"  Code interpreter events: {len(code_interpreter_events)}")
        print()
        
        # Test 3: Retrieve full response after streaming
        if response_id:
            print("TEST 3: RETRIEVE Full Response After Streaming")
            print("-" * 80)
            
            try:
                full_response = await openai_service.client.responses.retrieve(response_id)
                
                print("[OK] Full response retrieved")
                print(f"  Status: {full_response.status}")
                print(f"  Output items: {len(full_response.output) if hasattr(full_response, 'output') else 'N/A'}")
                print()
                
                # Check for code_interpreter_call outputs
                if hasattr(full_response, 'output'):
                    for i, item in enumerate(full_response.output):
                        print(f"  Output item {i}:")
                        print(f"    Type: {item.type}")
                        
                        if item.type == 'code_interpreter_call':
                            outputs = getattr(item, 'outputs', None)
                            print(f"    Has 'outputs' attribute: {outputs is not None}")
                            
                            # Debug: print ALL attributes
                            print(f"    Available attributes: {[a for a in dir(item) if not a.startswith('_')]}")
                            print(f"    Item dict: {item.__dict__ if hasattr(item, '__dict__') else 'N/A'}")
                            
                            if outputs:
                                print(f"    Number of outputs: {len(outputs)}")
                                for j, output in enumerate(outputs):
                                    print(f"      Output {j}: type={output.type}")
                                    if hasattr(output, 'file_id'):
                                        print(f"        file_id: {output.file_id}")
                                    if hasattr(output, 'url'):
                                        print(f"        url: {output.url}")
                            else:
                                print("    [ERROR] outputs is None or missing!")
                
            except Exception as e:
                print(f"[ERROR] Retrieve test failed: {e}")
        
        print()
        
    except Exception as e:
        print(f"[ERROR] Streaming test failed: {e}")
        print()
    
    print("=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    print("Based on the test results above:")
    print("1. Non-streaming response: outputs available? [CHECK RESULTS]")
    print("2. Streaming events: outputs available? [CHECK RESULTS]")
    print("3. Retrieved response after streaming: outputs available? [CHECK RESULTS]")
    print()

if __name__ == "__main__":
    asyncio.run(test_streaming_vs_nonstreaming())
