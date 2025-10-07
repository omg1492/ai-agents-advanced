"""
Adhoc test to verify code_interpreter file attachment format.
Tests the correct parameter name for passing files to code_interpreter container.
"""
import asyncio
import os
import io
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Load environment from .env file in current directory
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    
    # Initialize Azure OpenAI client (using OPENAI_* env vars)
    api_version = os.getenv("OPENAI_API_VERSION", "preview")
    if api_version == "preview":
        api_version = "2025-04-01-preview"
    
    client = AsyncAzureOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        api_version=api_version,
        azure_endpoint=os.getenv("OPENAI_BASE_URL", "").replace("/openai/v1/", "")
    )
    
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    
    print("=" * 80)
    print("Testing Code Interpreter File Attachment")
    print("=" * 80)
    
    # Step 1: Upload a test CSV file
    print("\n1. Uploading test CSV file...")
    csv_content = "name,weight\nJohn,70\nJane,65\nBob,80"
    csv_bytes = csv_content.encode('utf-8')
    
    file = await client.files.create(
        file=("test_weights.csv", io.BytesIO(csv_bytes), "text/csv"),
        purpose="assistants"
    )
    print(f"   ✓ File uploaded: {file.id}")
    
    # Step 2: Test with "file_ids" parameter (correct format based on community findings)
    print("\n2. Testing with 'file_ids' parameter...")
    try:
        response = await client.responses.create(
            model=model,
            tools=[
                {
                    "type": "code_interpreter",
                    "container": {
                        "type": "auto",
                        "file_ids": [file.id]  # Using file_ids (not files!)
                    }
                }
            ],
            input="Calculate the average weight from the CSV file.",
            store=True
        )
        print(f"   ✓ SUCCESS with 'file_ids': {response.id}")
        print(f"   Output: {response.output_text[:200]}...")
    except Exception as e:
        print(f"   ✗ FAILED with 'file_ids': {e}")
    
    # Step 3: Test with "files" parameter (documented but wrong)
    print("\n3. Testing with 'files' parameter (documented format)...")
    try:
        response = await client.responses.create(
            model=model,
            tools=[
                {
                    "type": "code_interpreter",
                    "container": {
                        "type": "auto",
                        "files": [file.id]  # Using files (documented but wrong!)
                    }
                }
            ],
            input="Calculate the average weight from the CSV file.",
            store=True
        )
        print(f"   ✓ SUCCESS with 'files': {response.id}")
        print(f"   Output: {response.output_text[:200]}...")
    except Exception as e:
        print(f"   ✗ FAILED with 'files': {e}")
    
    # Cleanup
    print("\n4. Cleaning up...")
    await client.files.delete(file.id)
    print(f"   ✓ File deleted: {file.id}")
    
    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
