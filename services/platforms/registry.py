"""
Platform service registry for dependency injection
"""

from typing import Dict, Type, Optional
from .base import BasePlatformService
from .instagram import InstagramService
from .twitter import TwitterService
from .youtube import YouTubeService
from .linkedin import LinkedInService


class PlatformRegistry:
    """Registry for platform services"""
    
    def __init__(self):
        self._services: Dict[str, Type[BasePlatformService]] = {
            "instagram": InstagramService,
            "twitter": TwitterService,
            "youtube": YouTubeService,
            "linkedin": LinkedInService,
        }
        self._instances: Dict[str, BasePlatformService] = {}
    
    def get_service(self, platform: str) -> Optional[BasePlatformService]:
        """Get platform service instance"""
        platform = platform.lower()
        
        if platform not in self._services:
            return None
        
        if platform not in self._instances:
            self._instances[platform] = self._services[platform]()
        
        return self._instances[platform]
    
    def list_platforms(self) -> list[str]:
        """List all supported platforms"""
        return list(self._services.keys())


# Global registry instance
platform_registry = PlatformRegistry()


def get_platform_service(platform: str) -> BasePlatformService:
    """Dependency injection function for platform services"""
    service = platform_registry.get_service(platform)
    if not service:
        raise ValueError(f"Unsupported platform: {platform}")
    return service
