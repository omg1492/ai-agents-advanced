"""Chef Agent client service for culinary services delegation.

Provides HTTP client for communicating with the specialized Chef Agent,
which handles chef search, catering services, availability checking, pricing,
and booking workflows.
"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class ChefAgentClient:
    """HTTP client for Chef Agent integration.
    
    The Chef Agent is a specialized service that uses remote MCP tools
    (Chef Services MCP) to provide culinary service assistance including:
    - Finding chefs by specialty and cuisine
    - Searching catering services
    - Checking availability
    - Calculating pricing
    - Placing orders
    """
    
    def __init__(self, base_url: str, timeout: float = 30.0):
        """Initialize Chef Agent client.
        
        Args:
            base_url: Base URL of Chef Agent API (e.g., http://localhost:8002)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"Chef Agent client initialized: url={self.base_url} timeout={timeout}s")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def query(self, message: str) -> str:
        """Send a query to the Chef Agent.
        
        Args:
            message: User's culinary service query
            
        Returns:
            Chef Agent's response text
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response is invalid
        """
        client = await self._get_client()
        
        logger.info("=" * 80)
        logger.info("🟢 DREAMFARM → CHEF: Delegating query to Chef Agent")
        logger.info("Target URL: %s/query", self.base_url)
        logger.info("Query (first 100 chars): %s", message[:100])
        
        try:
            logger.info("📤 DREAMFARM → CHEF: Sending HTTP POST request...")
            response = await client.post(
                f"{self.base_url}/query",
                json={"message": message},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            logger.info("✅ DREAMFARM ← CHEF: Received HTTP %d response", response.status_code)
            
            data = response.json()
            if "response" not in data:
                raise ValueError("Invalid response from Chef Agent: missing 'response' field")
            
            response_text = data["response"]
            logger.info("📥 DREAMFARM ← CHEF: Chef Agent responded")
            logger.info("Response length: %d characters", len(response_text))
            logger.info("Response preview (first 150 chars): %s", response_text[:150])
            logger.info("=" * 80)
            
            return response_text
            
        except httpx.HTTPStatusError as e:
            logger.error("❌ DREAMFARM ← CHEF: HTTP error %d - %s", e.response.status_code, e.response.text[:200])
            raise
        except httpx.RequestError as e:
            logger.error("❌ DREAMFARM ← CHEF: Request error: %s", e)
            raise
        except Exception as e:
            logger.error("❌ DREAMFARM ← CHEF: Query failed: %s", e)
            raise
    
    async def health_check(self) -> bool:
        """Check if Chef Agent is healthy and responding.
        
        Returns:
            True if healthy, False otherwise
        """
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            is_healthy = data.get("status") == "ok"
            logger.info(f"Chef Agent health check: healthy={is_healthy}")
            return is_healthy
        except Exception as e:
            logger.warning(f"Chef Agent health check failed: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("Chef Agent client closed")
