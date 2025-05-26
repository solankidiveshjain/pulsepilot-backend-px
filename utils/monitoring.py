"""
Monitoring and observability utilities with Sentry and Prometheus integration
"""

import os
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
except ImportError:
    sentry_sdk = None
    FastApiIntegration = None
    SqlalchemyIntegration = None
from prometheus_client import Counter, Histogram, Gauge
from typing import Dict, Any

from utils.config import get_config

try:
    config = get_config()
except Exception:
    config = None

# Prometheus metrics
REQUEST_COUNT = Counter(
    'pulsepilot_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'pulsepilot_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'pulsepilot_active_connections',
    'Number of active database connections'
)

TOKEN_USAGE = Counter(
    'pulsepilot_tokens_used_total',
    'Total tokens used',
    ['team_id', 'usage_type']
)

WEBHOOK_EVENTS = Counter(
    'pulsepilot_webhook_events_total',
    'Total webhook events processed',
    ['platform', 'status']
)


def init_sentry():
    """Initialize Sentry for error tracking"""
    if config.environment == "production":
        sentry_dsn = os.getenv("SENTRY_DSN")
        if sentry_dsn:
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[
                    FastApiIntegration(auto_enabling_integrations=False),
                    SqlalchemyIntegration(),
                ],
                traces_sample_rate=0.1,
                environment=config.environment,
                release=os.getenv("APP_VERSION", "unknown"),
            )


def track_request_metrics(method: str, endpoint: str, status_code: int, duration: float):
    """Track request metrics"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


def track_token_usage_metrics(team_id: str, usage_type: str, tokens: int):
    """Track token usage metrics"""
    TOKEN_USAGE.labels(team_id=team_id, usage_type=usage_type).inc(tokens)


def track_webhook_metrics(platform: str, status: str):
    """Track webhook processing metrics"""
    WEBHOOK_EVENTS.labels(platform=platform, status=status).inc()
