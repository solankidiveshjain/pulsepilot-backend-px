import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import tasks.reply_tasks as reply_module
from tasks.reply_tasks import submit_reply_to_platform
from models.database import Reply, Comment, SocialConnection
from services.social_platforms import get_platform_service

# Dummy context manager for session
class DummySessionCM:
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, exc_type, exc, tb):
        return False

@pytest.mark.asyncio
async def test_submit_reply_happy_path(monkeypatch, mock_db_session):
    # Arrange: create reply, comment, connection
    reply_id = uuid4()
    team_id = uuid4()
    platform = 'instagram'
    reply_obj = Reply(reply_id=reply_id, comment_id=uuid4(), user_id=uuid4(), message='Test reply')
    comment_obj = Comment(comment_id=reply_obj.comment_id, team_id=team_id,
                          platform=platform, author='user', message='msg',
                          metadata={'external_id':'ext123'})
    conn_obj = SocialConnection(connection_id=uuid4(), team_id=team_id,
                                platform=platform, status='connected', access_token='tok',
                                refresh_token=None, token_expires=None)
    # Stub DB: return reply, then comment, then connection
    select_result_reply = MagicMock()
    select_result_reply.scalar_one_or_none.return_value = reply_obj
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = comment_obj
    select_result_conn = MagicMock()
    select_result_conn.scalar_one_or_none.return_value = conn_obj
    mock_db_session.execute = AsyncMock(side_effect=[select_result_reply, select_result_comment, select_result_conn])
    monkeypatch.setattr(reply_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Stub platform service
    fake_service = MagicMock()
    fake_service.post_reply = AsyncMock(return_value={'id':'res'})
    monkeypatch.setattr(reply_module, 'get_platform_service', lambda p: fake_service)

    # Act
    await submit_reply_to_platform(reply_id, platform, team_id)

    # Assert: post_reply called with correct args
    fake_service.post_reply.assert_awaited_once_with(
        comment_id='ext123',
        message='Test reply',
        access_token='tok'
    )

@pytest.mark.asyncio
async def test_submit_reply_missing_reply(monkeypatch, mock_db_session):
    # Arrange: reply not found
    mock_db_session.execute = AsyncMock(return_value=type('R',(object,),{'scalar_one_or_none':lambda self: None})())
    monkeypatch.setattr(reply_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Spy on post_reply
    fake_service = MagicMock()
    monkeypatch.setattr(reply_module, 'get_platform_service', lambda p: fake_service)

    # Act
    await submit_reply_to_platform(uuid4(), 'insta', uuid4())

    # Assert: nothing called
    fake_service.post_reply.assert_not_called()

@pytest.mark.asyncio
async def test_submit_reply_missing_comment(monkeypatch, mock_db_session):
    # Arrange: reply found, comment missing
    reply_obj = Reply(reply_id=uuid4(), comment_id=uuid4(), user_id=uuid4(), message='r')
    # Stub DB: return reply then None for comment
    select_result_reply = MagicMock()
    select_result_reply.scalar_one_or_none.return_value = reply_obj
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(side_effect=[select_result_reply, select_result_comment])
    monkeypatch.setattr(reply_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    fake_service = MagicMock()
    monkeypatch.setattr(reply_module, 'get_platform_service', lambda p: fake_service)

    # Act
    await submit_reply_to_platform(reply_obj.reply_id, 'twitter', uuid4())
    fake_service.post_reply.assert_not_called()

@pytest.mark.asyncio
async def test_submit_reply_no_connection(monkeypatch, mock_db_session):
    # Arrange: reply and comment found, no connection
    reply_obj = Reply(reply_id=uuid4(), comment_id=uuid4(), user_id=uuid4(), message='r')
    comment_obj = Comment(comment_id=reply_obj.comment_id, team_id=uuid4(), platform='yt', author='u', message='m', metadata={'external_id':'e'})
    # Stub DB: return reply, comment, then None
    select_result_reply = MagicMock()
    select_result_reply.scalar_one_or_none.return_value = reply_obj
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = comment_obj
    select_result_conn = MagicMock()
    select_result_conn.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(side_effect=[select_result_reply, select_result_comment, select_result_conn])
    monkeypatch.setattr(reply_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    fake_service = MagicMock()
    monkeypatch.setattr(reply_module, 'get_platform_service', lambda p: fake_service)

    # Act
    await submit_reply_to_platform(reply_obj.reply_id, 'youtube', comment_obj.team_id)
    fake_service.post_reply.assert_not_called()

@pytest.mark.asyncio
async def test_submit_reply_unsupported_platform(monkeypatch, mock_db_session):
    # Arrange: reply, comment, connection found but no service instance
    reply_obj = Reply(reply_id=uuid4(), comment_id=uuid4(), user_id=uuid4(), message='r')
    comment_obj = Comment(comment_id=reply_obj.comment_id, team_id=uuid4(), platform='fb', author='u', message='m', metadata={'external_id':'e'})
    conn_obj = SocialConnection(connection_id=uuid4(), team_id=comment_obj.team_id, platform='fb', status='connected', access_token='t')
    # Stub DB: return reply, comment, connection
    select_result_reply = MagicMock()
    select_result_reply.scalar_one_or_none.return_value = reply_obj
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = comment_obj
    select_result_conn = MagicMock()
    select_result_conn.scalar_one_or_none.return_value = conn_obj
    mock_db_session.execute = AsyncMock(side_effect=[select_result_reply, select_result_comment, select_result_conn])
    monkeypatch.setattr(reply_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Simulate unsupported (returns None)
    monkeypatch.setattr(reply_module, 'get_platform_service', lambda p: None)

    # Act
    await submit_reply_to_platform(reply_obj.reply_id, 'facebook', comment_obj.team_id)
    # No exception, no post 