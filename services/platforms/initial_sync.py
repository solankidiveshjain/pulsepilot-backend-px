"""
Initial sync of posts and comments after a social platform connection.
"""

from uuid import UUID
from sqlalchemy import select
from models.database import SocialConnection, Post, Comment
from utils.database import get_session
from services.platforms.connectors import get_connector
from utils.task_queue import task_queue


async def initial_sync_social(connection_id: UUID):
    """Fetch initial data for a social connection and persist to the database."""
    async with get_session() as db:
        # Load the connection record
        result = await db.execute(
            select(SocialConnection).where(SocialConnection.connection_id == connection_id)
        )
        connection = result.scalar_one_or_none()
        if not connection or connection.status != 'connected':
            return

        # Instantiate the appropriate connector
        connector = get_connector(connection.platform, connection)
        if not connector:
            return

        # Fetch initial posts and comments
        posts_data, comments_data = await connector.fetch_initial()

        # Upsert posts and build mapping of external_id to Post
        posts_map: dict = {}
        for p in posts_data:
            # Check existing post by external_id
            stmt = select(Post).where(
                Post.external_id == p.external_id,
                Post.team_id == connection.team_id,
                Post.platform == p.platform
            )
            result = await db.execute(stmt)
            existing_post = result.scalar_one_or_none()
            if existing_post:
                # Update existing post
                existing_post.type = p.type
                existing_post.metadata_json = p.metadata
                await db.commit()
                await db.refresh(existing_post)
                posts_map[p.external_id] = existing_post
            else:
                # Create new post
                post = Post(
                    external_id=p.external_id,
                    team_id=connection.team_id,
                    platform=p.platform,
                    type=p.type,
                    metadata_json=p.metadata,
                    created_at=p.created_at
                )
                db.add(post)
                await db.commit()
                await db.refresh(post)
                posts_map[p.external_id] = post

        # Upsert comments linked to posts
        comment_models = []
        for c in comments_data:
            # Find associated post
            post_model = posts_map.get(c.post_external_id)
            # Check existing comment
            stmt_c = select(Comment).where(
                Comment.external_id == c.external_id,
                Comment.team_id == connection.team_id,
                Comment.platform == c.platform
            )
            res_c = await db.execute(stmt_c)
            existing_comment = res_c.scalar_one_or_none()
            if existing_comment:
                existing_comment.author = c.author
                existing_comment.message = c.message
                existing_comment.metadata_json = c.metadata
                existing_comment.post_id = post_model.post_id if post_model else None
                existing_comment.created_at = c.created_at
                db.add(existing_comment)
                comment_models.append(existing_comment)
            else:
                comment = Comment(
                    external_id=c.external_id,
                    team_id=connection.team_id,
                    platform=c.platform,
                    author=c.author,
                    message=c.message,
                    post_id=post_model.post_id if post_model else None,
                    metadata_json=c.metadata,
                    created_at=c.created_at
                )
                db.add(comment)
                comment_models.append(comment)
        await db.commit()

        # Schedule embedding and classification for comments asynchronously
        for comment in comment_models:
            await task_queue.enqueue_embedding_generation(comment.comment_id)
            await task_queue.enqueue_comment_classification(comment.comment_id) 