"""ThreadService tests deprecated.

All thread-based functionality has been removed in favor of /chat endpoint.
"""

import pytest


@pytest.mark.skip("ThreadService removed; use /chat API tests instead")
def test_thread_service_removed():
    assert True
