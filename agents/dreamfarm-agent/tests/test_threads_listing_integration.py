"""Integration tests for new /threads listing & hydration behavior.

Skips if conversations_raw table missing.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from src.main import app
from src.services.openai_service import OpenAIService

pytestmark = pytest.mark.integration


def _db_engine():
    url = f"postgresql://{os.getenv('PGUSER','admin')}:{os.getenv('PGPASSWORD','Admin12345678')}@{os.getenv('PGHOST','localhost')}:{os.getenv('PGPORT','5432')}/{os.getenv('PGDATABASE','aidb')}"
    return create_engine(url, echo=False)


def _has_table() -> bool:
    try:
        with _db_engine().connect() as conn:
            return bool(conn.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='conversations_raw' AND column_name='title'" )).fetchone())
    except Exception:
        return False


class TestThreadListingIntegration:
    @pytest.fixture
    def client(self):
        mock_service = Mock(spec=OpenAIService)
        mock_service.generate_response = AsyncMock(return_value=("Assistant", "resp_x"))
        with patch('src.main.OpenAIService', return_value=mock_service):
            with TestClient(app) as c:
                yield c

    def test_list_threads_and_hydrate(self, client):
        if not _has_table():
            pytest.skip("conversations_raw table (with title) not present")

        created_ids = []
        try:
            # Create two threads
            for name in ("List A", "List B"):
                r = client.post('/threads', json={'title': name})
                assert r.status_code == 200
                created_ids.append(r.json()['thread_id'])
            # Post a message to first to change ordering
            client.post(f"/threads/{created_ids[0]}/messages", json={'message': 'Hello'})
            # List threads
            list_res = client.get('/threads?limit=10&offset=0')
            assert list_res.status_code == 200
            threads = list_res.json()
            ids_in_list = [t['thread_id'] for t in threads]
            assert created_ids[0] in ids_in_list and created_ids[1] in ids_in_list
            # Delete local in-memory state artificially to test hydration
            from src.main import _threads, _history
            _threads.pop(created_ids[0], None)
            _history.pop(created_ids[0], None)
            # Get messages -> should hydrate from DB (not raising 404)
            msgs = client.get(f"/threads/{created_ids[0]}/messages")
            assert msgs.status_code == 200
            # Ensure thread metadata accessible
            meta = client.get(f"/threads/{created_ids[0]}")
            assert meta.status_code == 200
        finally:
            for tid in created_ids:
                client.delete(f"/threads/{tid}")
