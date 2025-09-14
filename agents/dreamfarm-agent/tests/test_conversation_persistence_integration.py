"""Integration test: store dummy conversation and delete it.

Requires database with conversations_raw table applied. Skips if table missing.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch

from src.main import app
from src.services.openai_service import OpenAIService

pytestmark = pytest.mark.integration


def _db_engine():
    url = f"postgresql://{os.getenv('PGUSER','admin')}:{os.getenv('PGPASSWORD','Admin12345678')}@{os.getenv('PGHOST','localhost')}:{os.getenv('PGPORT','5432')}/{os.getenv('PGDATABASE','aidb')}"
    return create_engine(url, echo=False)


def _has_table() -> bool:
    try:
        with _db_engine().connect() as conn:
            return bool(conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name='conversations_raw'" )).fetchone())
    except Exception:
        return False


class TestConversationPersistence:
    @pytest.fixture
    def client(self):
        mock_service = Mock(spec=OpenAIService)
        mock_service.generate_response = AsyncMock(return_value=("Assistant reply", "resp_1"))
        with patch('src.main.OpenAIService', return_value=mock_service):
            with TestClient(app) as c:
                yield c

    def test_store_and_delete(self, client):
        if not _has_table():
            pytest.skip("conversations_raw table not present")
        thread_id = None
        try:
            # Create thread
            r = client.post('/threads', json={'title': 'Persist Test'})
            assert r.status_code == 200
            thread_id = r.json()['thread_id']
            # Send two turns
            r1 = client.post(f'/threads/{thread_id}/messages', json={'message': 'Hi'})
            assert r1.status_code == 200
            r2 = client.post(f'/threads/{thread_id}/messages', json={'message': 'How are you?'})
            assert r2.status_code == 200
            # Verify DB has messages
            with _db_engine().connect() as conn:
                row = conn.execute(text('SELECT messages FROM conversations_raw WHERE thread_id=:t'), {'t': thread_id}).fetchone()
            assert row is not None
            assert len(row.messages) >= 2
            # Delete thread via API
            dr = client.delete(f'/threads/{thread_id}')
            assert dr.status_code == 200
            # Ensure removed from DB
            with _db_engine().connect() as conn:
                gone = conn.execute(text('SELECT 1 FROM conversations_raw WHERE thread_id=:t'), {'t': thread_id}).fetchone()
            assert gone is None
        finally:
            # Defensive cleanup: ensure row gone even if assertions above failed
            if thread_id:
                try:
                    client.delete(f'/threads/{thread_id}')
                except Exception:
                    pass
                try:
                    with _db_engine().begin() as conn:
                        conn.execute(text('DELETE FROM conversations_raw WHERE thread_id=:t'), {'t': thread_id})
                except Exception:
                    pass
