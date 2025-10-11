"""Quick local test script for Chef Agent API.

Run this while the Chef Agent is running on localhost:8002.
"""

import requests
import json

BASE_URL = "http://localhost:8002"


def test_health():
    """Test health endpoint."""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()


def test_query(message: str):
    """Test query endpoint."""
    print(f"Testing /query with message: '{message}'...")
    response = requests.post(
        f"{BASE_URL}/query",
        json={"message": message},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response ID: {data.get('response_id')}")
    print(f"Response text:\n{data.get('response')}")
    print()


if __name__ == "__main__":
    # Test health
    test_health()
    
    # Test queries
    test_query("Find me an Italian chef for a wedding")
    test_query("What catering services are available for 30 people?")
    test_query("Check availability for December 15th, 2025")
