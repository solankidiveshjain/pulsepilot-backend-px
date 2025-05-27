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
        """Use python-linkedin-v2 to fetch organization updates."""
        from linkedin_v2 import linkedin
        import asyncio
        token = self.connection.access_token
        app = linkedin.LinkedInApplication(token=token)
        # Expect organization ID saved in connection metadata
        org_id = self.connection.metadata.get('organization_id') if hasattr(self.connection, 'metadata') else None
        if not org_id:
            return [], []
        try:
            updates = await asyncio.to_thread(
                app.get_company_updates,
                organization_id=org_id,
                params={'count': 25}
            )
        except Exception:
            return [], []
        posts: List[PostData] = []
        comments: List[CommentData] = []
        for u in updates.get('values', []):
            # LinkedIn timestamps are in milliseconds
            ts = u.get('timestamp')
            created_at = None
            if ts:
                created_at = datetime.fromtimestamp(int(ts) / 1000)
            posts.append(PostData(
                external_id=str(u.get('updateKey', '')),
                platform='linkedin',
                type=u.get('updateType'),
                metadata=u,
                created_at=created_at
            ))
        return posts, comments

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch LinkedIn organization page statistics between two timestamps."""
        from utils.http_client import get_async_client
        from utils.config import get_config
        import asyncio
        # Prepare HTTP client and config
        client = get_async_client()
        config = get_config()
        base_url = config.linkedin_api_base_url
        token = self.connection.access_token
        # Determine organization URN
        org_id = self.connection.metadata.get('organization_id')
        if not org_id:
            return MetricsData(platform='linkedin', since=since, until=until, metrics={})
        org_urn = f"urn:li:organization:{org_id}"
        # Time interval in milliseconds
        start_ms = int(since.timestamp() * 1000)
        end_ms = int(until.timestamp() * 1000)
        # Prepare query parameters for LinkedIn metrics
        params = {
            'q': 'organization',
            'organization': org_urn,
            # LinkedIn expects timeIntervals as a string
            'timeIntervals': f"(timeRange:(start:{start_ms},end:{end_ms}),timeGranularityType:DAY)"
        }
        headers = {'Authorization': f"Bearer {token}"}
        try:
            resp = await client.get(f"{base_url}/organizationPageStatistics", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return MetricsData(platform='linkedin', since=since, until=until, metrics={})
        elements = data.get('elements', [])
        metrics: dict = {}
        for elem in elements:
            stats = elem.get('totalPageStatistics', {}) or {}
            for k, v in stats.items():
                if isinstance(v, dict):
                    metrics[k] = metrics.get(k, 0) + sum(v.values())
                else:
                    try:
                        metrics[k] = metrics.get(k, 0) + int(v)
                    except Exception:
                        pass
        return MetricsData(platform='linkedin', since=since, until=until, metrics=metrics)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch LinkedIn share-level statistics for a single post."""
        from utils.http_client import get_async_client
        from utils.config import get_config
        import asyncio
        client = get_async_client()
        config = get_config()
        base_url = config.linkedin_api_base_url
        token = self.connection.access_token
        org_id = self.connection.metadata.get('organization_id')
        if not org_id:
            return InsightsData(platform='linkedin', post_external_id=post_external_id, metrics={})
        share_urn = post_external_id
        # Prepare query parameters for LinkedIn share insights
        params = {
            'q': 'organizationalEntity',
            'organizationalEntity': f"urn:li:organization:{org_id}",
            # LinkedIn expects shares as a string or comma-separated list
            'shares': share_urn
        }
        headers = {'Authorization': f"Bearer {token}"}
        try:
            resp = await client.get(f"{base_url}/organizationalEntityShareStatistics", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return InsightsData(platform='linkedin', post_external_id=post_external_id, metrics={})
        elements = data.get('elements', [])
        metrics: dict = {}
        for elem in elements:
            stats = elem.get('shareStatistics', {}) or {}
            for k, v in stats.items():
                try:
                    metrics[k] = int(v)
                except Exception:
                    pass
        return InsightsData(platform='linkedin', post_external_id=post_external_id, metrics=metrics)

class YouTubeConnector(SocialMediaConnector):
    """Fetch initial videos and top comments from YouTube Data API"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Use google-api-python-client to fetch uploaded videos and comments."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import asyncio
        token = self.connection.access_token
        refresh = getattr(self.connection, 'refresh_token', None)
        # Build credentials object
        creds = Credentials(
            token=token,
            refresh_token=refresh,
            token_uri='https://oauth2.googleapis.com/token'
        )
        # Initialize YouTube service
        youtube = build('youtube', 'v3', credentials=creds)
        posts: List[PostData] = []
        comments: List[CommentData] = []
        try:
            # Get uploads playlist ID
            channels_resp = await asyncio.to_thread(
                youtube.channels().list,
                part='contentDetails',
                mine=True
            )
            channels_data = channels_resp.execute().get('items', [])
        except Exception:
            return [], []
        if not channels_data:
            return [], []
        uploads_id = channels_data[0]['contentDetails']['relatedPlaylists']['uploads']
        # Fetch videos from uploads playlist
        try:
            playlist_resp = await asyncio.to_thread(
                youtube.playlistItems().list,
                part='snippet',
                playlistId=uploads_id,
                maxResults=25
            )
            items = playlist_resp.execute().get('items', [])
        except Exception:
            items = []
        for pi in items:
            snippet = pi.get('snippet', {})
            vid_id = snippet.get('resourceId', {}).get('videoId')
            ts = snippet.get('publishedAt')
            created_at = datetime.fromisoformat(ts.replace('Z', '+00:00')) if ts else None
            posts.append(PostData(
                external_id=vid_id or '',
                platform='youtube',
                type='video',
                metadata=pi,
                created_at=created_at
            ))
            # Fetch top comments
            try:
                ct_resp = await asyncio.to_thread(
                    youtube.commentThreads().list,
                    part='snippet',
                    videoId=vid_id,
                    maxResults=25
                )
                threads = ct_resp.execute().get('items', [])
            except Exception:
                threads = []
            for th in threads:
                top = th.get('snippet', {}).get('topLevelComment', {}).get('snippet', {})
                cid = th.get('id')
                ts_c = top.get('publishedAt')
                c_at = datetime.fromisoformat(ts_c.replace('Z', '+00:00')) if ts_c else None
                comments.append(CommentData(
                    external_id=cid or '',
                    platform='youtube',
                    post_external_id=vid_id or '',
                    author=top.get('authorDisplayName'),
                    message=top.get('textOriginal'),
                    metadata=th,
                    created_at=c_at
                ))
        return posts, comments

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch channel-level metrics via YouTube Analytics API between two timestamps."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import asyncio
        # Build analytics service
        token = self.connection.access_token
        refresh = getattr(self.connection, 'refresh_token', None)
        creds = Credentials(
            token=token,
            refresh_token=refresh,
            token_uri='https://oauth2.googleapis.com/token'
        )
        analytics = build('youtubeAnalytics', 'v2', credentials=creds)
        metrics_dict = {'views': 0, 'likes': 0, 'comments': 0}
        try:
            resp = await asyncio.to_thread(
                analytics.reports().query,
                ids='channel==MINE',
                startDate=since.strftime('%Y-%m-%d'),
                endDate=until.strftime('%Y-%m-%d'),
                metrics=','.join(metrics_dict.keys())
            )
            data = resp.execute()
            for row in data.get('rows', []):
                # row format [date, views, likes, comments]
                for idx, key in enumerate(metrics_dict.keys(), start=1):
                    metrics_dict[key] += int(row[idx])
        except Exception:
            return MetricsData(platform='youtube', since=since, until=until, metrics={})
        return MetricsData(platform='youtube', since=since, until=until, metrics=metrics_dict)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch per-video statistics via YouTube Data API."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import asyncio
        token = self.connection.access_token
        refresh = getattr(self.connection, 'refresh_token', None)
        creds = Credentials(
            token=token,
            refresh_token=refresh,
            token_uri='https://oauth2.googleapis.com/token'
        )
        youtube = build('youtube', 'v3', credentials=creds)
        try:
            resp = await asyncio.to_thread(
                youtube.videos().list,
                part='statistics',
                id=post_external_id
            )
            items = resp.execute().get('items', [])
            stats = items[0].get('statistics', {}) if items else {}
            metrics = {k: int(v) for k, v in stats.items()}
        except Exception:
            return InsightsData(platform='youtube', post_external_id=post_external_id, metrics={})
        return InsightsData(platform='youtube', post_external_id=post_external_id, metrics=metrics)

class TikTokConnector(SocialMediaConnector):
    """Fetch initial videos and comments from TikTok"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Use TikTokApi to fetch user videos and comments."""
        from TikTokApi import TikTokApi
        import asyncio
        # Initialize TikTok API client
        api = TikTokApi.get_instance()
        # Expect user ID in metadata
        uid = self.connection.metadata.get('user_id') if hasattr(self.connection, 'metadata') else None
        if not uid:
            return [], []
        posts: List[PostData] = []
        comments: List[CommentData] = []
        try:
            videos = await asyncio.to_thread(api.user_posts, user_id=uid, count=25)
        except Exception:
            return [], []
        for v in videos:
            vid_id = str(v.get('id'))
            ts = v.get('createTime')
            created_at = datetime.fromtimestamp(ts) if ts else None
            posts.append(PostData(
                external_id=vid_id,
                platform='tiktok',
                type='video',
                metadata=v,
                created_at=created_at
            ))
            # Fetch comments for each video
            try:
                comms = await asyncio.to_thread(api.video_comments, video_id=vid_id, count=25)
            except Exception:
                comms = []
            for c in comms:
                cid = str(c.get('id'))
                c_ts = c.get('createTime')
                c_at = datetime.fromtimestamp(c_ts) if c_ts else None
                comments.append(CommentData(
                    external_id=cid,
                    platform='tiktok',
                    post_external_id=vid_id,
                    author=c.get('author', {}).get('uniqueId'),
                    message=c.get('text'),
                    metadata=c,
                    created_at=c_at
                ))
        return posts, comments

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch TikTok user video metrics between two timestamps by summing stats on user posts."""
        from TikTokApi import TikTokApi
        import asyncio
        # Initialize client
        api = TikTokApi.get_instance()
        uid = self.connection.metadata.get('user_id')
        if not uid:
            return MetricsData(platform='tiktok', since=since, until=until, metrics={})
        metrics: dict = {'playCount': 0, 'diggCount': 0, 'commentCount': 0, 'shareCount': 0}
        try:
            videos = await asyncio.to_thread(api.user_posts, user_id=uid, count=100)
            for v in videos:
                ts = v.get('createTime')
                from datetime import datetime
                created = datetime.fromtimestamp(ts) if ts else None
                if created and since <= created <= until:
                    # extract stats from video dict
                    stats = v.get('stats', v)
                    for k in list(metrics.keys()):
                        val = stats.get(k)
                        if isinstance(val, (int, float)):
                            metrics[k] += val
        except Exception:
            return MetricsData(platform='tiktok', since=since, until=until, metrics={})
        return MetricsData(platform='tiktok', since=since, until=until, metrics=metrics)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch TikTok video-level statistics for a single video."""
        from TikTokApi import TikTokApi
        import asyncio
        api = TikTokApi.get_instance()
        try:
            info = await asyncio.to_thread(api.video, id=post_external_id)
            stats = info.get('stats', info)
            metrics = {k: stats.get(k) for k in ['playCount', 'diggCount', 'commentCount', 'shareCount'] if stats.get(k) is not None}
        except Exception:
            return InsightsData(platform='tiktok', post_external_id=post_external_id, metrics={})
        return InsightsData(platform='tiktok', post_external_id=post_external_id, metrics=metrics)

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