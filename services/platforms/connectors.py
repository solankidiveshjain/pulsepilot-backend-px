"""
Connector interface for fetching posts/comments on initial connect (Phase 1)
"""

from abc import ABC, abstractmethod
from typing import Tuple, List, Optional
from models.database import SocialConnection
from schemas.social_media import PostData, CommentData, MetricsData, InsightsData, PostCreate, PostUpdate, VideoUpload
from facebook import GraphAPI, GraphAPIError
from datetime import datetime
import asyncio
from utils.http_client import get_async_client
from utils.social_settings import get_social_media_settings
import httpx


class SocialMediaConnector(ABC):
    """Abstract base class for social media data connectors"""

    def __init__(self, connection: SocialConnection):
        """Initialize connector with stored SocialConnection instance."""
        self.connection = connection

    @abstractmethod
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Fetch recent posts and comments for initial data sync."""
        pass

    @abstractmethod
    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch engagement metrics between two timestamps."""
        pass

    @abstractmethod
    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch detailed insights for a given post."""
        pass

# Platform-specific connector stubs
class FacebookConnector(SocialMediaConnector):
    """Fetch initial posts/comments from Facebook"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Delegate to FacebookService for initial post/comment sync."""
        from services.platforms.facebook import FacebookService
        svc = FacebookService()
        return await svc.fetch_initial(self.connection.access_token)

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Delegate to FacebookService for page-level metrics."""
        from services.platforms.facebook import FacebookService
        svc = FacebookService()
        return await svc.fetch_metrics(self.connection.access_token, since, until)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Delegate to FacebookService for post-level insights."""
        from services.platforms.facebook import FacebookService
        svc = FacebookService()
        return await svc.fetch_insights(self.connection.access_token, post_external_id)

class InstagramConnector(SocialMediaConnector):
    """Fetch initial media and comments from Instagram Graph API"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Delegate to InstagramService for initial media/comment sync."""
        from services.platforms.instagram import InstagramService
        svc = InstagramService()
        return await svc.fetch_initial(self.connection.access_token)

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Delegate to InstagramService for profile-level metrics."""
        from services.platforms.instagram import InstagramService
        svc = InstagramService()
        return await svc.fetch_metrics(self.connection.access_token, since, until)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Delegate to InstagramService for media-level insights."""
        from services.platforms.instagram import InstagramService
        svc = InstagramService()
        return await svc.fetch_insights(self.connection.access_token, post_external_id)

class TwitterConnector(SocialMediaConnector):
    """Fetch initial tweets and replies from Twitter API v2"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Delegate to TwitterService for initial tweets and replies sync."""
        from services.platforms.twitter import TwitterService
        svc = TwitterService()
        return await svc.fetch_initial(self.connection.access_token)

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Delegate to TwitterService for aggregated tweet metrics."""
        from services.platforms.twitter import TwitterService
        svc = TwitterService()
        return await svc.fetch_metrics(self.connection.access_token, since, until)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Delegate to TwitterService for tweet public metrics."""
        from services.platforms.twitter import TwitterService
        svc = TwitterService()
        return await svc.fetch_insights(self.connection.access_token, post_external_id)

class LinkedInConnector(SocialMediaConnector):
    """Fetch initial shares/updates from LinkedIn"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Delegate to LinkedInService for initial share/comment sync."""
        from services.platforms.linkedin import LinkedInService
        svc = LinkedInService()
        org_id = self.connection.metadata.get('organization_id')
        return await svc.fetch_initial(self.connection.access_token, org_id)

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Delegate to LinkedInService for organization-level metrics."""
        from services.platforms.linkedin import LinkedInService
        svc = LinkedInService()
        org_id = self.connection.metadata.get('organization_id')
        return await svc.fetch_metrics(self.connection.access_token, since, until, org_id)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Delegate to LinkedInService for share-level insights."""
        from services.platforms.linkedin import LinkedInService
        svc = LinkedInService()
        org_id = self.connection.metadata.get('organization_id')
        return await svc.fetch_insights(self.connection.access_token, post_external_id, org_id)

class YouTubeConnector(SocialMediaConnector):
    """Fetch initial videos and top comments from YouTube Data API"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Delegate to YouTubeService for initial videos/comments sync."""
        from services.platforms.youtube import YouTubeService
        svc = YouTubeService()
        return await svc.fetch_initial(
            self.connection.access_token,
            getattr(self.connection, 'refresh_token', None)
        )

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Delegate to YouTubeService for channel-level metrics."""
        from services.platforms.youtube import YouTubeService
        svc = YouTubeService()
        return await svc.fetch_metrics(
            self.connection.access_token,
            since,
            until,
            getattr(self.connection, 'refresh_token', None)
        )

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Delegate to YouTubeService for per-video insights."""
        from services.platforms.youtube import YouTubeService
        svc = YouTubeService()
        return await svc.fetch_insights(
            self.connection.access_token,
            post_external_id,
            getattr(self.connection, 'refresh_token', None)
        )

class TikTokConnector(SocialMediaConnector):
    """Fetch initial videos and comments from TikTok"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Delegate to TikTokService for initial videos/comments sync."""
        from services.platforms.tiktok import TikTokService
        svc = TikTokService()
        user_id = self.connection.metadata.get('user_id')
        return await svc.fetch_initial(
            self.connection.access_token,
            user_id
        )

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Delegate to TikTokService for aggregated video metrics."""
        from services.platforms.tiktok import TikTokService
        svc = TikTokService()
        user_id = self.connection.metadata.get('user_id')
        return await svc.fetch_metrics(
            self.connection.access_token,
            since,
            until,
            user_id
        )

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Delegate to TikTokService for video-level insights."""
        from services.platforms.tiktok import TikTokService
        svc = TikTokService()
        user_id = self.connection.metadata.get('user_id')
        return await svc.fetch_insights(
            self.connection.access_token,
            post_external_id,
            user_id
        )

# Connector registry
CONNECTORS = {
    "facebook": FacebookConnector,
    "instagram": InstagramConnector,
    "twitter": TwitterConnector,
    "linkedin": LinkedInConnector,
    "youtube": YouTubeConnector,
    "tiktok": TikTokConnector,
}

def get_connector(platform: str, connection: SocialConnection) -> Optional[SocialMediaConnector]:
    """Factory to get connector instance by platform"""
    connector_cls = CONNECTORS.get(platform.lower())
    if not connector_cls:
        return None
    return connector_cls(connection) 