import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import tasks.embedding_tasks as embedding_module
from tasks.embedding_tasks import generate_comment_embedding, batch_generate_embeddings
from services.vector_service import VectorService
from models.database import Comment, Reply

# Unique ID for testing embed calls
TEST_COMMENT_ID = uuid4()

class DummySessionCM:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False

@pytest.mark.asyncio
async def test_generate_embedding_combines_comment_and_replies(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment with two replies
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.message = "Hello world"
    sample_replies = [
        Reply(comment_id=TEST_COMMENT_ID, reply_id=uuid4(), message="First reply"),
        Reply(comment_id=TEST_COMMENT_ID, reply_id=uuid4(), message="Second reply")
    ]

    # Stub DB execute: return comment then replies
    select_result_comment = MagicMock()
    select_result_comment.scalar_one_or_none.return_value = sample_comment
    select_result_replies = MagicMock()
    select_result_replies.scalars.return_value = MagicMock(all=lambda: sample_replies)
    mock_db_session.execute = AsyncMock(side_effect=[select_result_comment, select_result_replies])
    monkeypatch.setattr(embedding_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Capture the combined text
    captured = {}
    async def fake_generate_embedding(self, text):
        captured['text'] = text
        return [0.123] * 384
    monkeypatch.setattr(VectorService, 'generate_embedding', fake_generate_embedding)

    # Spy on upsert calls
    recorded = []
    async def fake_upsert(session, model, values, pk_field):
        recorded.append((model, values, pk_field))
    monkeypatch.setattr(embedding_module, 'upsert', fake_upsert)

    # Act
    await generate_comment_embedding(TEST_COMMENT_ID)

    # Assert combined text contains comment and replies
    assert "Hello world" in captured['text']
    assert "First reply" in captured['text']
    assert "Second reply" in captured['text']

    # Assert upsert called correctly
    assert recorded, "Upsert should have been called"
    model, values, pk = recorded[0]
    assert model is Comment
    assert values['comment_id'] == TEST_COMMENT_ID
    assert isinstance(values['embedding'], list) and len(values['embedding']) == 384
    assert pk == 'comment_id'

@pytest.mark.asyncio
async def test_generate_embedding_skips_if_already_embedded(monkeypatch, mock_db_session, sample_comment):
    # Arrange: comment already has embedding
    sample_comment.comment_id = TEST_COMMENT_ID
    sample_comment.message = "Already embedded"
    sample_comment.embedding = [0.0] * 384

    # Stub DB execute: return comment with existing embedding
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = sample_comment
    mock_db_session.execute = AsyncMock(return_value=select_result)
    monkeypatch.setattr(embedding_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Spy on vector generation and upsert
    monkeypatch.setattr(VectorService, 'generate_embedding', AsyncMock())
    monkeypatch.setattr(embedding_module, 'upsert', AsyncMock())

    # Act
    await generate_comment_embedding(TEST_COMMENT_ID)

    # Assert neither vector nor upsert were called
    VectorService.generate_embedding.assert_not_called()
    embedding_module.upsert.assert_not_called()

@pytest.mark.asyncio
async def test_generate_embedding_gracefully_handles_missing_comment(monkeypatch, mock_db_session):
    # Arrange: no comment found
    # Stub DB execute: return no comment
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=select_result)
    monkeypatch.setattr(embedding_module, 'get_session', lambda: DummySessionCM(mock_db_session))
    monkeypatch.setattr(VectorService, 'generate_embedding', AsyncMock())
    monkeypatch.setattr(embedding_module, 'upsert', AsyncMock())

    # Act
    await generate_comment_embedding(TEST_COMMENT_ID)

    # Assert no calls when comment missing
    VectorService.generate_embedding.assert_not_called()
    embedding_module.upsert.assert_not_called()

@pytest.mark.asyncio
async def test_batch_generate_embeddings_calls_generate_comment_embedding(monkeypatch, mock_db_session, sample_team_id):
    # Arrange: two comments without embeddings
    c1 = Comment(comment_id=uuid4(), team_id=sample_team_id, message="One", embedding=None)
    c2 = Comment(comment_id=uuid4(), team_id=sample_team_id, message="Two", embedding=None)

    # Stub DB execute: return two comments without embeddings
    select_scalars = MagicMock()
    select_scalars.all.return_value = [c1, c2]
    select_result = MagicMock()
    select_result.scalars.return_value = select_scalars
    mock_db_session.execute = AsyncMock(return_value=select_result)
    monkeypatch.setattr(embedding_module, 'get_session', lambda: DummySessionCM(mock_db_session))

    # Spy on generate_comment_embedding
    called = []
    async def fake_generate(cid):
        called.append(cid)
    monkeypatch.setattr(embedding_module, 'generate_comment_embedding', fake_generate)

    # Act
    await batch_generate_embeddings(sample_team_id, limit=2)

    # Assert it was called for each comment
    assert set(called) == {c1.comment_id, c2.comment_id} 