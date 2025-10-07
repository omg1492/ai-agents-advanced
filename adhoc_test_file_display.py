"""
Adhoc test to check code_interpreter file event ordering.
This helps diagnose why sandbox URLs aren't being replaced.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION", "preview"),
    azure_endpoint=os.getenv("OPENAI_BASE_URL", "").rstrip("/openai/v1/").rstrip("/openai/v1"),
)

# Upload a test CSV
csv_content = """date,weight
2024-01-01,75.2
2024-01-02,75.0
2024-01-03,74.8
2024-01-04,74.9
2024-01-05,74.7"""

import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    f.write(csv_content)
    csv_path = f.name

try:
    # Upload file
    print("Uploading file...")
    with open(csv_path, 'rb') as f:
        file_obj = client.files.create(file=f, purpose="assistants")
    print(f"File uploaded: {file_obj.id}")
    
    # Create a response that generates a plot
    print("\nCreating response with code_interpreter...")
    
    generated_files = {}  # Track filename -> file_id mapping
    
    stream = client.responses.stream(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[{
            "role": "user",
            "content": "Create a line plot of the weight over time from the CSV data.",
            "attachments": [{
                "file_id": file_obj.id,
                "tools": [{"type": "code_interpreter"}]
            }]
        }],
        tools=[{"type": "code_interpreter", "container": {"type": "auto"}}]
    )
    
    print("\nEvent stream:")
    print("-" * 80)
    
    text_deltas = []
    output_items = []
    
    for event in stream:
        event_type = event.type
        print(f"[{event_type}]", end="")
        
        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", "")
            text_deltas.append((len(text_deltas), delta))
            if "sandbox:" in delta:
                print(f" ⚠️  SANDBOX URL IN TEXT: {delta[:100]}")
            else:
                print(f" text: {delta[:50]}")
        
        elif event_type == "response.output_item.done":
            item = getattr(event, "item", None)
            if item:
                item_type = getattr(item, "type", None)
                output_items.append((len(output_items), item_type, item))
                print(f" item_type={item_type}")
                
                if item_type == "code_interpreter_call":
                    outputs = getattr(item, "outputs", [])
                    print(f"   → {len(outputs)} outputs")
                    for output in outputs:
                        output_type = getattr(output, "type", None)
                        if output_type == "image":
                            file_id = getattr(output, "file_id", None)
                            url = getattr(output, "url", "")
                            print(f"   → Image: file_id={file_id}, url={url}")
                            
                            # Extract filename
                            import re
                            match = re.search(r'/mnt/data/([a-zA-Z0-9_\-\.]+)', url)
                            if match:
                                filename = match.group(1)
                                generated_files[filename] = file_id
                                print(f"   → Mapped: {filename} -> {file_id}")
        else:
            print()
    
    print("-" * 80)
    print(f"\n📊 Analysis:")
    print(f"  Total text deltas: {len(text_deltas)}")
    print(f"  Total output items: {len(output_items)}")
    print(f"  Generated files mapping: {generated_files}")
    
    # Check if any text delta with sandbox URL came before file mapping
    print(f"\n🔍 Checking order:")
    for idx, delta in text_deltas:
        if "sandbox:" in delta:
            print(f"  Text delta #{idx} contains sandbox URL")
            print(f"  Generated files at that point: {generated_files}")
    
finally:
    os.unlink(csv_path)
    print(f"\n✅ Test complete")
