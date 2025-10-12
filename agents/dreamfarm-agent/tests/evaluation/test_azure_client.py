"""Test Azure OpenAI client configuration."""
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

# Load .env from agent root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Get configuration
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
api_version = os.getenv("OPENAI_API_VERSION")
model = os.getenv("OPENAI_MODEL")

print("="*80)
print("Testing Azure OpenAI Client Configuration")
print("="*80)
print(f"Base URL from .env: {base_url}")
print(f"API Version: {api_version}")
print(f"Model: {model}")
print()

# Extract azure_endpoint
if base_url and "/openai/v1" in base_url:
    azure_endpoint = base_url.split("/openai/v1")[0] + "/"
else:
    azure_endpoint = base_url

print(f"Extracted Azure Endpoint: {azure_endpoint}")
print()

# Test the client
client = AsyncAzureOpenAI(
    api_key=api_key,
    azure_endpoint=azure_endpoint,
    api_version=api_version,
)

async def test_call():
    try:
        print("Calling Azure OpenAI API...")
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say hello in exactly 3 words"}],
            temperature=0.0,
        )
        print(f"✓ Success!")
        print(f"Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(test_call())
print()
print("="*80)
print(f"Test result: {'PASSED ✓' if result else 'FAILED ✗'}")
print("="*80)
