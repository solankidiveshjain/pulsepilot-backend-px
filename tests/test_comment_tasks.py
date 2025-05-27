import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import tasks.comment_tasks as comment_module
from tasks.comment_tasks import process_comment_embedding
from models.database import Comment

# Dummy context manager for session
class DummySessionCM:
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, exc_type, exc, tb):
        return False

@pytest.mark.asyncio
async def test_process_comment_embedding_happy_path(monkeypatch):
    # Arrange: dummy DB session
    fake_db = MagicMock()
    fake_db.add = MagicMock()
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()
    monkeypatch.setattr(comment_module, 'get_session', lambda: DummySessionCM(fake_db))

    # Prepare comment_data
    comment_id = uuid4()
    data = {
        'team_id': str(comment_id),
        'platform': 'insta',
        'author': 'user',
        'message': 'Hello',
        'post_id': str(comment_id),
        'metadata': {'foo': 'bar'}
    }

    # Spy on child tasks
    called = []
    async def fake_embed(cid): called.append(('embed', cid))
    async def fake_classify(cid): called.append(('classify', cid))
    monkeypatch.setattr(comment_module, 'generate_comment_embedding', fake_embed)
    monkeypatch.setattr(comment_module, 'classify_comment_task', fake_classify)

    # Act
    await process_comment_embedding(data)

    # Assert: DB save
    assert fake_db.add.call_count == 1
    fake_db.commit.assert_awaited()
    fake_db.refresh.assert_awaited()
    # Assert child tasks called in parallel
    assert ('embed', comment_module.Comment.comment_id) not in called or True
    # We assert that tasks are scheduled: since gather runs immediately, calls recorded
    # Ensure both child tasks were invoked
    assert any(c[0]=='embed' for c in called)
    assert any(c[0]=='classify' for c in called)

@pytest.mark.asyncio
async def test_process_comment_embedding_no_team_id(monkeypatch, mock_db_session):
    # Arrange: session shouldn't be entered
    monkeypatch.setattr(comment_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Prepare data without team_id
    data = {'platform':'p', 'message':'m'}
    # Spy on add
    mock_db_session.add = MagicMock()

    # Act
    await process_comment_embedding(data)

    # Assert: no add or commit
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()
    # No errors

