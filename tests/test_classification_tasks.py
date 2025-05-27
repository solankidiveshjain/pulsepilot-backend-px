import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import tasks.classification_tasks as classification_module
from tasks.classification_tasks import classify_comment, batch_classify_comments
from models.database import Comment

# Dummy context manager for session
class DummySessionCM:
    def __init__(self, session):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, exc_type, exc, tb):
        return False

# Unique ID for tests
TEST_COMMENT_ID = uuid4()

@pytest.mark.asyncio
async def test_classify_comment_happy_path(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment without prior classification
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.message = "Great product!"
    sample_comment.platform = "instagram"
    object.__setattr__(sample_comment, 'metadata', {})  # ensure no classification exists

    # Stub DB: select returns our sample_comment, update call returns None
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = sample_comment
    mock_db_session.execute = AsyncMock(side_effect=[select_result, None])
    # Provide our session context
    monkeypatch.setattr(classification_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Stub classification service
    fake_service = MagicMock()
    classification_result = {
        "sentiment": "positive",
        "emotion": "joy",
        "category": "compliment",
        "confidence": 0.95
    }
    fake_service.classify_comment = AsyncMock(return_value=classification_result)
    monkeypatch.setattr(classification_module, 'ClassificationService', lambda: fake_service)

    # Spy on update builder
    update_calls = []
    class FakeStmt:
        def __init__(self, model):
            self.model = model
        def where(self, clause):
            return self
        def values(self, **kwargs):
            update_calls.append((self.model, kwargs))
            return self
    monkeypatch.setattr(classification_module, 'update', lambda model: FakeStmt(model))

    # Stub token tracker
    fake_tracker = MagicMock()
    fake_tracker.track_usage = AsyncMock()
    monkeypatch.setattr(classification_module, 'TokenTracker', lambda: fake_tracker)

    # Act
    await classify_comment(TEST_COMMENT_ID)

    # Assert: classification was called correctly
    fake_service.classify_comment.assert_awaited_once_with(sample_comment.message, sample_comment.platform)
    # Assert: update called with metadata including classification
    assert update_calls, "Expected update to be called"
    model, kwargs = update_calls[0]
    assert model is Comment
    metadata = kwargs.get("metadata", {})
    assert metadata.get("classification") == classification_result

    # Assert commit was called
    mock_db_session.commit.assert_awaited_once()
    # Assert token usage tracked
    expected_tokens = len(sample_comment.message.split())
    expected_cost = 0.0002 * expected_tokens
    fake_tracker.track_usage.assert_awaited_once_with(
        team_id=sample_comment.team_id,
        usage_type="classification",
        tokens_used=expected_tokens,
        cost=expected_cost
    )

@pytest.mark.asyncio
async def test_classify_comment_skips_if_already_classified(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment already has classification
    sample_comment.comment_id = TEST_COMMENT_ID
    object.__setattr__(sample_comment, 'metadata', {"classification": {"sentiment": "neutral"}})

    # Stub DB: select returns our sample_comment
    select_result2 = MagicMock()
    select_result2.scalar_one_or_none.return_value = sample_comment
    mock_db_session.execute = AsyncMock(return_value=select_result2)
    monkeypatch.setattr(classification_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Spy classification service and token tracker
    fake_service = MagicMock()
    fake_service.classify_comment = AsyncMock()
    monkeypatch.setattr(classification_module, 'ClassificationService', lambda: fake_service)
    fake_tracker = MagicMock()
    fake_tracker.track_usage = AsyncMock()
    monkeypatch.setattr(classification_module, 'TokenTracker', lambda: fake_tracker)

    # Spy on update builder
    update_calls = []
    class FakeStmt2:
        def __init__(self, model): pass
        def where(self, clause): return self
        def values(self, **kwargs):
            update_calls.append((model, kwargs))
            return self
    monkeypatch.setattr(classification_module, 'update', lambda model: FakeStmt2(model))

    # Act
    await classify_comment(TEST_COMMENT_ID)

    # Assert: nothing was called after select
    fake_service.classify_comment.assert_not_awaited()
    mock_db_session.commit.assert_not_awaited()
    assert not update_calls, "Update should not be called"
    fake_tracker.track_usage.assert_not_awaited()

@pytest.mark.asyncio
async def test_classify_comment_gracefully_handles_missing_comment(monkeypatch, mock_db_session):
    # Arrange: no comment found
    # Stub DB: select returns None
    select_result3 = MagicMock()
    select_result3.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=select_result3)
    monkeypatch.setattr(classification_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Spy classification service and token tracker
    fake_service = MagicMock()
    fake_service.classify_comment = AsyncMock()
    monkeypatch.setattr(classification_module, 'ClassificationService', lambda: fake_service)
    fake_tracker = MagicMock()
    fake_tracker.track_usage = AsyncMock()
    monkeypatch.setattr(classification_module, 'TokenTracker', lambda: fake_tracker)

    # Act
    await classify_comment(TEST_COMMENT_ID)

    # Assert: classification and update not called
    fake_service.classify_comment.assert_not_awaited()
    mock_db_session.commit.assert_not_awaited()
    fake_tracker.track_usage.assert_not_awaited()

@pytest.mark.asyncio
async def test_batch_classify_comments_calls_classify_for_unclassified(monkeypatch, mock_db_session, sample_team_id):
    # Arrange: one classified and one unclassified
    c1 = Comment(comment_id=uuid4(), team_id=sample_team_id, message="Msg1", metadata={"classification": {}})
    c2 = Comment(comment_id=uuid4(), team_id=sample_team_id, message="Msg2", metadata={})

    # Stub DB: execute returns result with scalars().all() => [c1, c2]
    select_scalars = MagicMock()
    select_scalars.all.return_value = [c1, c2]
    select_result = MagicMock()
    select_result.scalars.return_value = select_scalars
    mock_db_session.execute = AsyncMock(return_value=select_result)
    monkeypatch.setattr(classification_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Spy on classify_comment
    calls = []
    async def fake_classify(cid):
        calls.append(cid)
    monkeypatch.setattr(classification_module, 'classify_comment', fake_classify)

    # Act
    await batch_classify_comments(sample_team_id, limit=2)

    # Assert only unclassified comment is processed
    assert calls == [c2.comment_id] 