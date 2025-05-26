"""
Unit tests for platform service registry - critical for platform abstraction
"""

import pytest
from unittest.mock import MagicMock, patch

from services.platforms.registry import PlatformRegistry, get_platform_service
from services.platforms.base import BasePlatformService


class TestPlatformRegistry:
    """Test platform service registry for dependency injection"""

    def test_get_service_returns_singleton_instance(self):
        """
        Business Critical: Ensures platform services are singletons to prevent
        configuration drift and maintain connection state consistency
        """
        registry = PlatformRegistry()
        
        # Get same service twice
        service1 = registry.get_service("instagram")
        service2 = registry.get_service("instagram")
        
        # Should return same instance
        assert service1 is service2
        assert service1 is not None

    def test_get_service_case_insensitive(self):
        """
        Business Critical: Platform names from webhooks may have inconsistent casing
        """
        registry = PlatformRegistry()
        
        service_lower = registry.get_service("instagram")
        service_upper = registry.get_service("INSTAGRAM")
        service_mixed = registry.get_service("Instagram")
        
        assert service_lower is service_upper is service_mixed

    def test_get_service_unsupported_platform_returns_none(self):
        """
        Business Critical: Graceful handling of unsupported platforms prevents crashes
        """
        registry = PlatformRegistry()
        
        service = registry.get_service("unsupported_platform")
        
        assert service is None

    def test_list_platforms_returns_all_supported(self):
        """
        Business Critical: API documentation and frontend need accurate platform list
        """
        registry = PlatformRegistry()
        
        platforms = registry.list_platforms()
        
        expected_platforms = ["instagram", "twitter", "youtube", "linkedin"]
        assert set(platforms) == set(expected_platforms)

    def test_get_platform_service_dependency_injection_success(self):
        """
        Business Critical: Dependency injection must work for FastAPI endpoints
        """
        service = get_platform_service("instagram")
        
        assert service is not None
        assert hasattr(service, 'platform_name')
        assert service.platform_name == "instagram"

    def test_get_platform_service_dependency_injection_failure(self):
        """
        Business Critical: Invalid platform should raise clear error for debugging
        """
        with pytest.raises(ValueError, match="Unsupported platform: invalid"):
            get_platform_service("invalid")


class TestPlatformServiceInterface:
    """Test that all platform services implement required interface"""

    @pytest.mark.parametrize("platform", ["instagram", "twitter", "youtube", "linkedin"])
    def test_platform_service_implements_interface(self, platform):
        """
        Business Critical: All platform services must implement the same interface
        for consistent webhook processing and connection management
        """
        service = get_platform_service(platform)
        
        # Check required methods exist
        assert hasattr(service, 'platform_name')
        assert hasattr(service, 'validate_connection')
        assert hasattr(service, 'connect_team')
        assert hasattr(service, 'disconnect_team')
        assert hasattr(service, 'process_webhook')
        assert hasattr(service, 'verify_webhook_signature')
        assert hasattr(service, 'post_reply')
        
        # Check platform_name is correct
        assert service.platform_name == platform
