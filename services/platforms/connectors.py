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

    @abstractmethod
    async def create_post(self, payload: PostCreate) -> PostData:
        """Create a new post on the platform."""
        pass

    @abstractmethod
    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        """Update an existing post on the platform."""
        pass

    @abstractmethod
    async def delete_post(self, post_external_id: str) -> bool:
        """Delete a post from the platform."""
        pass

    @abstractmethod
    async def upload_video(self, payload: VideoUpload) -> PostData:
        """Upload a video to the platform."""
        pass

# Platform-specific connector stubs
class FacebookConnector(SocialMediaConnector):
    """Fetch initial posts/comments from Facebook"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Fetch recent posts and comments with a single nested Graph API call."""
        token = self.connection.access_token
        graph = GraphAPI(access_token=token, version='16.0')

        # Define nested fields for posts and comments
        fields = (
            'posts.limit(25){'
            'id,created_time,type,message,comments.limit(25){'
            'id,created_time,from,message'
            '}}'
        )
        try:
            # Execute sync call in a thread pool per SDK guidance
            resp = await asyncio.to_thread(graph.get_object, 'me', fields=fields)
        except GraphAPIError:
            # Gracefully handle Graph API errors
            return [], []

        posts_data = resp.get('posts', {}).get('data', [])
        posts: List[PostData] = []
        comments: List[CommentData] = []

        for item in posts_data:
            ct = item.get('created_time')
            created_at = datetime.fromisoformat(ct.replace('Z', '+00:00')) if ct else None
            posts.append(PostData(
                external_id=item.get('id', ''),
                platform='facebook',
                type=item.get('type'),
                metadata=item,
                created_at=created_at
            ))
            # Parse nested comments
            for c in item.get('comments', {}).get('data', []):
                ctime = c.get('created_time')
                c_at = datetime.fromisoformat(ctime.replace('Z', '+00:00')) if ctime else None
                comments.append(CommentData(
                    external_id=c.get('id', ''),
                    platform='facebook',
                    post_external_id=item.get('id', ''),
                    author=c.get('from', {}).get('name'),
                    message=c.get('message'),
                    metadata=c,
                    created_at=c_at
                ))
        return posts, comments

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch page-level engagement metrics between two timestamps."""
        token = self.connection.access_token
        graph = GraphAPI(access_token=token, version='16.0')
        metric_names = ['page_impressions', 'page_engaged_users', 'page_consumptions']
        try:
            resp = await asyncio.to_thread(
                graph.get_connections,
                'me',
                'insights',
                metric=','.join(metric_names),
                since=int(since.timestamp()),
                until=int(until.timestamp())
            )
        except GraphAPIError:
            return MetricsData(platform='facebook', since=since, until=until, metrics={})
        data = resp.get('data', [])
        metrics = {}
        for entry in data:
            name = entry.get('name')
            total = 0
            for v in entry.get('values', []):
                val = v.get('value', 0)
                if isinstance(val, dict):
                    total += sum(val.values())
                else:
                    total += val
            if name:
                metrics[name] = total
        return MetricsData(platform='facebook', since=since, until=until, metrics=metrics)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch per-post detailed insights (impressions, engagements, reactions)."""
        token = self.connection.access_token
        graph = GraphAPI(access_token=token, version='16.0')
        metric_names = ['post_impressions', 'post_engaged_users', 'post_reactions_by_type_total']
        try:
            resp = await asyncio.to_thread(
                graph.get_connections,
                post_external_id,
                'insights',
                metric=','.join(metric_names),
                period='lifetime'
            )
        except GraphAPIError:
            return InsightsData(platform='facebook', post_external_id=post_external_id, metrics={})
        data = resp.get('data', [])
        metrics = {}
        for entry in data:
            name = entry.get('name')
            total = 0
            for v in entry.get('values', []):
                val = v.get('value', 0)
                if isinstance(val, dict):
                    total += sum(val.values())
                else:
                    total += val
            if name:
                metrics[name] = total
        return InsightsData(platform='facebook', post_external_id=post_external_id, metrics=metrics)

    async def create_post(self, payload: PostCreate) -> PostData:
        raise NotImplementedError("FacebookConnector.create_post not implemented")

    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        raise NotImplementedError("FacebookConnector.update_post not implemented")

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError("FacebookConnector.delete_post not implemented")

    async def upload_video(self, payload: VideoUpload) -> PostData:
        raise NotImplementedError("FacebookConnector.upload_video not implemented")

class InstagramConnector(SocialMediaConnector):
    """Fetch initial media and comments from Instagram Graph API"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Fetch recent media entries and nested comments via Graph API."""
        token = self.connection.access_token
        graph = GraphAPI(access_token=token, version='16.0')
        # Define nested fields: media and comments
        fields = (
            'media.limit(25){'
            'id,caption,media_type,permalink,timestamp,'
            'comments.limit(25){id,text,timestamp,username}'
            '}'
        )
        try:
            resp = await asyncio.to_thread(graph.get_connections, 'me', 'media', fields=fields)
        except GraphAPIError:
            return [], []
        media_data = resp.get('data', [])
        posts: List[PostData] = []
        comments: List[CommentData] = []
        for item in media_data:
            ts = item.get('timestamp')
            created_at = datetime.fromisoformat(ts.replace('Z', '+00:00')) if ts else None
            posts.append(PostData(
                external_id=item.get('id', ''),
                platform='instagram',
                type=item.get('media_type'),
                metadata=item,
                created_at=created_at
            ))
            # Nested comments
            for c in item.get('comments', {}).get('data', []):
                cts = c.get('timestamp')
                c_at = datetime.fromisoformat(cts.replace('Z', '+00:00')) if cts else None
                comments.append(CommentData(
                    external_id=c.get('id', ''),
                    platform='instagram',
                    post_external_id=item.get('id', ''),
                    author=c.get('username'),
                    message=c.get('text'),
                    metadata=c,
                    created_at=c_at
                ))
        return posts, comments

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch Instagram profile-level metrics between two timestamps."""
        token = self.connection.access_token
        graph = GraphAPI(access_token=token, version='16.0')
        metric_names = ['impressions', 'reach', 'profile_views']
        try:
            resp = await asyncio.to_thread(
                graph.get_connections,
                'me',
                'insights',
                metric=','.join(metric_names),
                period='day',
                since=int(since.timestamp()),
                until=int(until.timestamp())
            )
        except GraphAPIError:
            return MetricsData(platform='instagram', since=since, until=until, metrics={})
        data = resp.get('data', [])
        metrics = {}
        for entry in data:
            name = entry.get('name')
            total = 0
            for v in entry.get('values', []):
                val = v.get('value', 0)
                if isinstance(val, dict):
                    total += sum(val.values())
                else:
                    total += val
            if name:
                metrics[name] = total
        return MetricsData(platform='instagram', since=since, until=until, metrics=metrics)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch media-level detailed insights (impressions, reach, engagement)."""
        token = self.connection.access_token
        graph = GraphAPI(access_token=token, version='16.0')
        metric_names = ['impressions', 'reach', 'engagement']
        try:
            resp = await asyncio.to_thread(
                graph.get_connections,
                post_external_id,
                'insights',
                metric=','.join(metric_names),
                period='lifetime'
            )
        except GraphAPIError:
            return InsightsData(platform='instagram', post_external_id=post_external_id, metrics={})
        data = resp.get('data', [])
        metrics = {}
        for entry in data:
            name = entry.get('name')
            total = 0
            for v in entry.get('values', []):
                val = v.get('value', 0)
                if isinstance(val, dict):
                    total += sum(val.values())
                else:
                    total += val
            if name:
                metrics[name] = total
        return InsightsData(platform='instagram', post_external_id=post_external_id, metrics=metrics)

    async def create_post(self, payload: PostCreate) -> PostData:
        raise NotImplementedError("InstagramConnector.create_post not implemented")

    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        raise NotImplementedError("InstagramConnector.update_post not implemented")

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError("InstagramConnector.delete_post not implemented")

    async def upload_video(self, payload: VideoUpload) -> PostData:
        raise NotImplementedError("InstagramConnector.upload_video not implemented")

class TwitterConnector(SocialMediaConnector):
    """Fetch initial tweets and replies from Twitter API v2"""
    async def fetch_initial(self) -> Tuple[List[PostData], List[CommentData]]:
        """Use tweepy AsyncClient with Paginator to fetch tweets and replies."""
        from tweepy.asynchronous import AsyncClient
        from tweepy import Paginator
        from tweepy.errors import TweepyException
        # Initialize async client
        token = self.connection.access_token
        client = AsyncClient(bearer_token=token)
        try:
            user_resp = await client.get_me()
            user_id = user_resp.data.id
        except TweepyException:
            return [], []

        posts: List[PostData] = []
        comments: List[CommentData] = []
        try:
            # Fetch user tweets
            async for resp in Paginator(
                client.get_users_tweets,
                id=user_id,
                max_results=25,
                tweet_fields=['created_at','conversation_id'],
            ):
                for t in resp.data or []:
                    posts.append(PostData(
                        external_id=str(t.id),
                        platform='twitter',
                        type='text',
                        metadata=t.data,
                        created_at=t.created_at
                    ))
                    # Fetch replies (tweets in same conversation)
                    conv_id = str(t.conversation_id or t.id)
                    async for r_resp in Paginator(
                        client.search_recent_tweets,
                        query=f'conversation_id:{conv_id}',
                        max_results=25,
                        tweet_fields=['created_at','author_id','text']
                    ):
                        for r in r_resp.data or []:
                            comments.append(CommentData(
                                external_id=str(r.id),
                                platform='twitter',
                                post_external_id=str(t.id),
                                author=str(r.author_id),
                                message=r.text,
                                metadata=r.data,
                                created_at=r.created_at
                            ))
        except TweepyException:
            # Handle rate limit or other errors
            pass
        return posts, comments

    async def fetch_metrics(self, since: datetime, until: datetime) -> MetricsData:
        """Fetch aggregated tweet metrics between two timestamps."""
        from tweepy.asynchronous import AsyncClient
        from tweepy import Paginator
        from tweepy.errors import TweepyException
        token = self.connection.access_token
        client = AsyncClient(bearer_token=token)
        try:
            user_resp = await client.get_me()
            user_id = user_resp.data.id
        except TweepyException:
            return MetricsData(platform='twitter', since=since, until=until, metrics={})
        metrics = {'retweet_count': 0, 'reply_count': 0, 'like_count': 0, 'quote_count': 0}
        try:
            async for resp in Paginator(
                client.get_users_tweets,
                id=user_id,
                start_time=since.isoformat(),
                end_time=until.isoformat(),
                tweet_fields=['public_metrics'],
                max_results=100
            ):
                for t in resp.data or []:
                    pm = t.data.get('public_metrics', {})
                    for k in metrics:
                        metrics[k] += pm.get(k, 0)
        except TweepyException:
            pass
        return MetricsData(platform='twitter', since=since, until=until, metrics=metrics)

    async def fetch_insights(self, post_external_id: str) -> InsightsData:
        """Fetch tweet public_metrics for a single tweet."""
        from tweepy.asynchronous import AsyncClient
        from tweepy.errors import TweepyException
        token = self.connection.access_token
        client = AsyncClient(bearer_token=token)
        try:
            resp = await client.get_tweet(id=post_external_id, tweet_fields=['public_metrics'])
            pm = resp.data.public_metrics
            metrics = {
                'retweet_count': pm.get('retweet_count', 0),
                'reply_count': pm.get('reply_count', 0),
                'like_count': pm.get('like_count', 0),
                'quote_count': pm.get('quote_count', 0)
            }
        except Exception:
            return InsightsData(platform='twitter', post_external_id=post_external_id, metrics={})
        return InsightsData(platform='twitter', post_external_id=post_external_id, metrics=metrics)

    async def create_post(self, payload: PostCreate) -> PostData:
        raise NotImplementedError("TwitterConnector.create_post not implemented")

    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        raise NotImplementedError("TwitterConnector.update_post not implemented")

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError("TwitterConnector.delete_post not implemented")

    async def upload_video(self, payload: VideoUpload) -> PostData:
        raise NotImplementedError("TwitterConnector.upload_video not implemented")

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

    async def create_post(self, payload: PostCreate) -> PostData:
        raise NotImplementedError("LinkedInConnector.create_post not implemented")

    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        raise NotImplementedError("LinkedInConnector.update_post not implemented")

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError("LinkedInConnector.delete_post not implemented")

    async def upload_video(self, payload: VideoUpload) -> PostData:
        raise NotImplementedError("LinkedInConnector.upload_video not implemented")

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

    async def create_post(self, payload: PostCreate) -> PostData:
        raise NotImplementedError("YouTubeConnector.create_post not implemented")

    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        raise NotImplementedError("YouTubeConnector.update_post not implemented")

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError("YouTubeConnector.delete_post not implemented")

    async def upload_video(self, payload: VideoUpload) -> PostData:
        raise NotImplementedError("YouTubeConnector.upload_video not implemented")

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

    async def create_post(self, payload: PostCreate) -> PostData:
        raise NotImplementedError("TikTokConnector.create_post not implemented")

    async def update_post(self, post_external_id: str, payload: PostUpdate) -> PostData:
        raise NotImplementedError("TikTokConnector.update_post not implemented")

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError("TikTokConnector.delete_post not implemented")

    async def upload_video(self, payload: VideoUpload) -> PostData:
        raise NotImplementedError("TikTokConnector.upload_video not implemented")

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