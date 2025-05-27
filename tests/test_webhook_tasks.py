import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import tasks.webhook_tasks as webhook_module
from tasks.webhook_tasks import WebhookProcessingTask
from services.platforms.base import CommentData
from utils.exceptions import PlatformError

# Dummy context manager for session
class DummySessionCM:
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, exc_type, exc, tb):
        return False

@pytest.mark.asyncio
async def test_webhook_processing_happy_path(monkeypatch, mock_db_session, sample_team_id):
    # Arrange
    # Prepare fake comment data returned by platform service
    cd1 = CommentData(
        external_id="ext1",
        author="user1",
        message="Hello",
        post_id="post1",
        platform_metadata={"foo": "bar"}
    )
    cd2 = CommentData(
        external_id="ext2",
        author="user2",
        message="World",
        post_id="post2",
        platform_metadata={}
    )
    fake_service = MagicMock()
    fake_service.ingest_webhook = AsyncMock(return_value=[cd1, cd2])
    monkeypatch.setattr(webhook_module, 'get_platform_service', lambda platform: fake_service)

    # Stub session context
    mock_db = mock_db_session
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db))

    # Stub task queue
    queued = []
    class FakeQueue:
        def add_task(self, coro): queued.append(coro)
    monkeypatch.setattr(webhook_module, 'task_queue', FakeQueue())

    # Payload data
    payload_data = {
        'headers': {'h': 'v'},
        'body': b'body',
        'json_data': {'raw': 'data'},
        'team_id': sample_team_id
    }

    # Act
    task = WebhookProcessingTask()
    comment_ids = await task.execute('instagram', payload_data)

    # Assert returned IDs for two comments
    assert isinstance(comment_ids, list) and len(comment_ids) == 2
    # Assert DB operations called twice
    assert mock_db.add.call_count == 2
    assert mock_db.commit.await_count == 2
    assert mock_db.refresh.await_count == 2
    # Assert tasks queued: embedding and classification per comment
    assert len(queued) == 4

@pytest.mark.asyncio
async def test_webhook_processing_no_comments(monkeypatch, mock_db_session, sample_team_id):
    # Arrange: service returns no comments
    fake_service = MagicMock()
    fake_service.ingest_webhook = AsyncMock(return_value=[])
    monkeypatch.setattr(webhook_module, 'get_platform_service', lambda platform: fake_service)
    # Stub session (should not be entered)
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Stub queue
    queued = []
    class FakeQueue:
        def add_task(self, coro): queued.append(coro)
    monkeypatch.setattr(webhook_module, 'task_queue', FakeQueue())
    payload_data = {'headers': {}, 'body': b'', 'json_data': {}, 'team_id': sample_team_id}

    # Act
    task = WebhookProcessingTask()
    comment_ids = await task.execute('twitter', payload_data)

    # Assert empty result and no ops
    assert comment_ids == []
    assert mock_db_session.add.call_count == 0
    assert mock_db_session.commit.await_count == 0
    assert mock_db_session.refresh.await_count == 0
    assert queued == []

@pytest.mark.asyncio
async def test_webhook_processing_wraps_exceptions(monkeypatch):
    # Arrange: ingest_webhook raises
    fake_service = MagicMock()
    fake_service.ingest_webhook = AsyncMock(side_effect=Exception('fail'))
    monkeypatch.setattr(webhook_module, 'get_platform_service', lambda platform: fake_service)
    # No need to stub session
    payload_data = {'headers': {}, 'body': b'', 'json_data': {}, 'team_id': uuid4()}

    # Act & Assert
    task = WebhookProcessingTask()
    with pytest.raises(PlatformError) as excinfo:
        await task.execute('linkedin', payload_data)
    # Check message and details
    assert 'Webhook processing failed for linkedin' in str(excinfo.value)
    assert 'fail' in excinfo.value.details.get('error', '') 