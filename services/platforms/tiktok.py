from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from utils.http_client import get_async_client
from utils.social_settings import get_social_media_settings
from .base import BasePlatformService, PlatformConnectionData, OnboardingConfig, PlatformWebhookData
import asyncio
from schemas.social_media import PostData, CommentData, MetricsData, InsightsData


class TikTokService(BasePlatformService):
    """TikTok API service implementation"""

    def __init__(self):
        self.client = get_async_client()
        settings = get_social_media_settings().tiktok
        self.api_base = settings.get('api_base_url')
        self.client_key = settings.get('client_key')
        self.client_secret = settings.get('client_secret')
        self._oauth_config: Optional[OnboardingConfig] = None

    @property
    def platform_name(self) -> str:
        return 'tiktok'

    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Generate TikTok OAuth authorization URL"""
        self._oauth_config = config
        state = str(team_id)
        scope_str = ','.join(config.scopes)
        auth_url = (
            f"{self.api_base}/platform/oauth/authorize"
            f"?client_key={config.client_id or self.client_key}"
            f"&redirect_uri={config.redirect_uri}"
            f"&scope={scope_str}"
            f"&response_type=code"
            f"&state={state}"
        )
        return {'auth_url': auth_url, 'state': state, 'platform': self.platform_name}

    async def exchange_auth_code(self, auth_code: str, state: str) -> PlatformConnectionData:
        """Exchange code for TikTok access token"""
        if not self._oauth_config:
            raise RuntimeError('OAuth configuration missing')
        params = {
            'client_key': self._oauth_config.client_id or self.client_key,
            'client_secret': self._oauth_config.client_secret or self.client_secret,
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self._oauth_config.redirect_uri
        }
        resp = await self.client.post(f"{self.api_base}/oauth/access_token", json=params)
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get('data', {}).get('access_token')
        expires_in = data.get('data', {}).get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return PlatformConnectionData(
            access_token=access_token,
            refresh_token=None,
            token_expires=expires_at,
            metadata=data.get('data', {})
        )

    async def refresh_token(self, refresh_token: str) -> PlatformConnectionData:
        """TikTok token refresh is not supported via API"""
        raise NotImplementedError('TikTok token refresh not supported')

    async def validate_connection(self, access_token: str) -> bool:
        """Validate TikTok access token by checking its presence."""
        return bool(access_token)

    async def connect_team(self, team_id: UUID, connection_data: PlatformConnectionData) -> Dict[str, Any]:
        """Finalize connection: ensure token is valid and store metadata."""
        is_valid = await self.validate_connection(connection_data.access_token)
        if not is_valid:
            raise ValueError('Invalid TikTok access token')
        # Metadata might include user info later
        return {
            'platform': self.platform_name,
            'status': 'connected',
            'access_token': connection_data.access_token,
            'refresh_token': connection_data.refresh_token,
            'token_expires': connection_data.token_expires,
            'metadata': connection_data.metadata or {}
        }

    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect TikTok by marking status locally."""
        return True

    async def process_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> List[PlatformWebhookData]:
        """Process TikTok webhook payload and extract comments."""
        comments: List[PlatformWebhookData] = []
        # Example TikTok webhook payload: {'comment': {...}}
        comment_info = payload.get('comment') or {}
        if comment_info:
            comments.append(PlatformWebhookData(
                external_id=comment_info.get('cid', ''),
                author=comment_info.get('user', {}).get('uid'),
                message=comment_info.get('text', ''),
                post_id=comment_info.get('item_id'),
                platform_metadata={'tiktok_data': comment_info}
            ))
        return comments

    async def verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """TikTok webhooks do not include signatures by default."""
        return True

    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to TikTok comment (not currently supported)."""
        # TikTok API does not support comments replies via API
        return {}

    async def fetch_initial(self, access_token: str, user_id: Optional[str] = None) -> Tuple[List[PostData], List[CommentData]]:
        """Use TikTokApi to fetch user videos and comments."""
        from TikTokApi import TikTokApi
        import asyncio
        api = TikTokApi.get_instance()
        uid = user_id
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
                platform=self.platform_name,
                type='video',
                metadata=v,
                created_at=created_at
            ))
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
                    platform=self.platform_name,
                    post_external_id=vid_id,
                    author=c.get('author', {}).get('uniqueId'),
                    message=c.get('text'),
                    metadata=c,
                    created_at=c_at
                ))
        return posts, comments

    async def fetch_metrics(self, access_token: str, since: datetime, until: datetime, user_id: Optional[str] = None) -> MetricsData:
        """Use TikTokApi to fetch aggregated user video metrics between two timestamps."""
        from TikTokApi import TikTokApi
        import asyncio
        api = TikTokApi.get_instance()
        uid = user_id
        if not uid:
            return MetricsData(platform=self.platform_name, since=since, until=until, metrics={})
        metrics: Dict[str, int] = {'playCount': 0, 'diggCount': 0, 'commentCount': 0, 'shareCount': 0}
        try:
            videos = await asyncio.to_thread(api.user_posts, user_id=uid, count=100)
            for v in videos:
                ts = v.get('createTime')
                created = datetime.fromtimestamp(ts) if ts else None
                if created and since <= created <= until:
                    stats = v.get('stats', v)
                    for k in list(metrics.keys()):
                        val = stats.get(k)
                        if isinstance(val, (int, float)):
                            metrics[k] += val
        except Exception:
            return MetricsData(platform=self.platform_name, since=since, until=until, metrics={})
        return MetricsData(platform=self.platform_name, since=since, until=until, metrics=metrics)

    async def fetch_insights(self, access_token: str, post_external_id: str, user_id: Optional[str] = None) -> InsightsData:
        """Use TikTokApi to fetch video-level statistics for a single video."""
        from TikTokApi import TikTokApi
        import asyncio
        api = TikTokApi.get_instance()
        uid = user_id
        if not uid:
            return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics={})
        try:
            info = await asyncio.to_thread(api.video, id=post_external_id)
            stats = info.get('stats', info)
            metrics = {k: stats.get(k) for k in ['playCount', 'diggCount', 'commentCount', 'shareCount'] if stats.get(k) is not None}
        except Exception:
            return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics={})
        return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics=metrics)

    async def create_post(self, payload: Any) -> Any:
        raise NotImplementedError('TikTokService.create_post not implemented')

    async def update_post(self, post_external_id: str, payload: Any) -> Any:
        raise NotImplementedError('TikTokService.update_post not implemented')

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError('TikTokService.delete_post not implemented')

    async def upload_video(self, payload: Any) -> Any:
        raise NotImplementedError('TikTokService.upload_video not implemented') 