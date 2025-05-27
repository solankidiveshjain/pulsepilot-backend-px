import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import tasks.webhook_tasks as webhook_module
from tasks.webhook_tasks import EmbeddingGenerationTask, CommentClassificationTask
from models.database import Comment, Reply
from utils.exceptions import DatabaseError

# Dummy context manager for session
class DummySessionCM:
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, exc_type, exc, tb):
        return False

# Common test ID
TEST_COMMENT_ID = uuid4()

@pytest.mark.asyncio
async def test_embedding_generation_execute_happy_path(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment with text and no existing embedding
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.team_id = sample_comment.team_id
    sample_comment.message = "Hello embed"
    sample_comment.embedding = None
    # Two replies to include
    replies = [
        Reply(comment_id=TEST_COMMENT_ID, reply_id=uuid4(), user_id=uuid4(), message="R1"),
        Reply(comment_id=TEST_COMMENT_ID, reply_id=uuid4(), user_id=uuid4(), message="R2")
    ]

    # Stub DB execute: return comment, replies, then update result
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = sample_comment
    select_result_replies = MagicMock()
    select_result_replies.scalars.return_value = MagicMock(all=lambda: replies)
    select_result_update = MagicMock()
    mock_db_session.execute = AsyncMock(side_effect=[select_result_comment, select_result_replies, select_result_update])
    mock_db_session.commit = AsyncMock()
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Capture embedding input text
    captured = {}
    class FakeVS:
        async def generate_embedding(self, text):
            captured['text'] = text
            return [0.1, 0.2, 0.3]
    # Patch VectorService import resolution
    import services.vector_service as vs_mod
    monkeypatch.setattr(vs_mod, 'VectorService', FakeVS)

    # Patch token tracker
    class FakeTracker:
        def __init__(self): self.calls = []
        async def track_usage(self, team_id, usage_type, tokens_used, cost):
            self.calls.append((team_id, usage_type, tokens_used, cost))
    fake_tracker = FakeTracker()
    import utils.token_tracker as tt_mod
    monkeypatch.setattr(tt_mod, 'TokenTracker', lambda: fake_tracker)

    # Act
    task = EmbeddingGenerationTask()
    result = await task.execute(TEST_COMMENT_ID)

    # Assert
    assert result is True
    # Embedding text combines comment + replies
    assert "Hello embed" in captured['text']
    assert "R1" in captured['text'] and "R2" in captured['text']
    # DB calls: select, select replies, update
    assert mock_db_session.execute.await_count == 3
    mock_db_session.commit.assert_awaited_once()
    # Token tracker called with correct counts
    tokens = len(captured['text'].split())
    assert fake_tracker.calls == [(
        sample_comment.team_id, 'embedding', tokens, pytest.approx(0.0001 * tokens)
    )]

@pytest.mark.asyncio
async def test_embedding_generation_skips_if_no_comment_or_message(monkeypatch, mock_db_session):
    # Arrange: no comment found
    # Stub DB execute: return no comment
    select_result_missing = MagicMock()
    select_result_missing.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=select_result_missing)
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Act
    task = EmbeddingGenerationTask()
    result = await task.execute(TEST_COMMENT_ID)

    # Assert
    assert result is False
    mock_db_session.execute.assert_awaited_once()

@pytest.mark.asyncio
async def test_embedding_generation_skips_if_already_embedded(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment exists with embedding
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.message = "msg"
    sample_comment.embedding = [0.0]
    # Stub DB execute: return comment with embedding
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = sample_comment
    mock_db_session.execute = AsyncMock(return_value=select_result)
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Act
    task = EmbeddingGenerationTask()
    result = await task.execute(TEST_COMMENT_ID)

    # Assert skip
    assert result is True
    mock_db_session.execute.assert_awaited_once()

@pytest.mark.asyncio
async def test_embedding_generation_exception_wrapped(monkeypatch, mock_db_session, sample_comment):
    # Arrange: vector service raises
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.message = "hi"
    sample_comment.embedding = None
    # Stub DB execute: return comment then no replies
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = sample_comment
    select_result_replies = MagicMock()
    select_result_replies.scalars.return_value = []
    mock_db_session.execute = AsyncMock(side_effect=[select_result_comment, select_result_replies])
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Patch VectorService to throw
    import services.vector_service as vs_mod
    class BadVS:
        async def generate_embedding(self, text):
            raise ValueError('oops')
    monkeypatch.setattr(vs_mod, 'VectorService', BadVS)

    task = EmbeddingGenerationTask()
    with pytest.raises(DatabaseError) as ei:
        await task.execute(TEST_COMMENT_ID)
    assert 'Embedding generation failed for comment' in str(ei.value)

@pytest.mark.asyncio
async def test_comment_classification_execute_happy_path(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment text and no prior classification
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.team_id = sample_comment.team_id
    sample_comment.platform = 'insta'
    sample_comment.message = 'Hello classify'
    object.__setattr__(sample_comment, 'metadata', {})
    # Replies
    replies = [Reply(comment_id=TEST_COMMENT_ID, reply_id=uuid4(), user_id=uuid4(), message='A')] 
    # Stub DB exec: return comment, replies, then update result
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = sample_comment
    select_result_replies = MagicMock()
    select_result_replies.scalars.return_value = MagicMock(all=lambda: replies)
    select_result_update = MagicMock()
    mock_db_session.execute = AsyncMock(side_effect=[select_result_comment, select_result_replies, select_result_update])
    mock_db_session.commit = AsyncMock()
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Stub classification service and capture text & platform
    captured = {}
    class FakeCS:
        async def classify_comment(self, text, platform):
            captured['text'] = text
            captured['platform'] = platform
            return {'sentiment':'a','emotion':'b','category':'c','confidence':0.5}
    import services.classification_service as cs_mod
    monkeypatch.setattr(cs_mod, 'ClassificationService', lambda: FakeCS())

    # Stub token tracker
    fake_tracker = MagicMock()
    fake_tracker.track_usage = AsyncMock()
    import utils.token_tracker as tt_mod2
    monkeypatch.setattr(tt_mod2, 'TokenTracker', lambda: fake_tracker)

    # Act
    task = CommentClassificationTask()
    result = await task.execute(TEST_COMMENT_ID)

    # Assert
    assert result is True
    # Combined text
    assert 'Hello classify' in captured['text'] and 'A' in captured['text']
    assert captured['platform'] == 'insta'
    assert mock_db_session.execute.await_count == 3
    mock_db_session.commit.assert_awaited_once()
    tokens = len(captured['text'].split())
    # Assert token usage tracked
    fake_tracker.track_usage.assert_awaited_once_with(
        team_id=sample_comment.team_id,
        usage_type='classification',
        tokens_used=tokens,
        cost=pytest.approx(0.0002 * tokens)
    )

@pytest.mark.asyncio
async def test_comment_classification_skips_if_already_classified(monkeypatch, mock_db_session, sample_comment):
    # Arrange: metadata already has classification
    sample_comment.comment_id = TEST_COMMENT_ID
    object.__setattr__(sample_comment, 'metadata', {'classification':{}})
    # Stub DB: return the sample_comment
    select_result2 = MagicMock()
    select_result2.scalar_one_or_none.return_value = sample_comment
    mock_db_session.execute = AsyncMock(return_value=select_result2)
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Act
    task = CommentClassificationTask()
    result = await task.execute(TEST_COMMENT_ID)
    # Assert skip
    assert result is True
    mock_db_session.execute.assert_awaited_once()

@pytest.mark.asyncio
async def test_comment_classification_handles_missing_comment(monkeypatch, mock_db_session):
    # Arrange: no comment
    # Stub DB: return no comment
    select_result3 = MagicMock()
    select_result3.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=select_result3)
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    # Act
    task = CommentClassificationTask()
    result = await task.execute(TEST_COMMENT_ID)
    assert result is False

@pytest.mark.asyncio
async def test_comment_classification_exception_wrapped(monkeypatch, mock_db_session, sample_comment):
    # Arrange: classifier throws
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.message = 'msg'
    object.__setattr__(sample_comment, 'metadata', {})
    # Stub DB: return comment then no replies
    select_result_comment2 = MagicMock()
    select_result_comment2.scalar_one_or_none.return_value = sample_comment
    select_result_replies2 = MagicMock()
    select_result_replies2.scalars.return_value = []
    mock_db_session.execute = AsyncMock(side_effect=[select_result_comment2, select_result_replies2])
    monkeypatch.setattr(webhook_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    import services.classification_service as cs_mod2
    class BadCS:
        async def classify_comment(self, text, platform):
            raise RuntimeError('bad')
    monkeypatch.setattr(cs_mod2, 'ClassificationService', lambda: BadCS())

    task = CommentClassificationTask()
    with pytest.raises(DatabaseError):
        await task.execute(TEST_COMMENT_ID) 