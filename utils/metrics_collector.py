"""
Prometheus metrics collection for monitoring
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from typing import Dict, Any
import time

from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class MetricsCollector:
    """Prometheus metrics collector for PulsePilot"""
    
    def __init__(self):
        """Initialize metrics collector with Prometheus metrics"""
        self.registry = CollectorRegistry()
        
        # API Request metrics
        self.request_count = Counter(
            'pulsepilot_requests_total',
            'Total number of API requests',
            ['method', 'endpoint', 'status_code', 'team_id'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            'pulsepilot_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # LLM/AI metrics
        self.llm_requests = Counter(
            'pulsepilot_llm_requests_total',
            'Total LLM API requests',
            ['model', 'operation', 'team_id'],
            registry=self.registry
        )
        
        self.llm_latency = Histogram(
            'pulsepilot_llm_latency_seconds',
            'LLM request latency',
            ['model', 'operation'],
            registry=self.registry
        )
        
        self.llm_tokens = Counter(
            'pulsepilot_llm_tokens_total',
            'Total LLM tokens used',
            ['model', 'token_type', 'team_id'],
            registry=self.registry
        )
        
        self.llm_cost = Counter(
            'pulsepilot_llm_cost_total',
            'Total LLM cost in USD',
            ['model', 'team_id'],
            registry=self.registry
        )
        
        # Platform integration metrics
        self.platform_requests = Counter(
            'pulsepilot_platform_requests_total',
            'Platform API requests',
            ['platform', 'operation', 'status'],
            registry=self.registry
        )
        
        self.webhook_events = Counter(
            'pulsepilot_webhook_events_total',
            'Webhook events processed',
            ['platform', 'status'],
            registry=self.registry
        )
        
        # Background task metrics
        self.task_queue_size = Gauge(
            'pulsepilot_task_queue_size',
            'Number of tasks in queue',
            ['queue_name'],
            registry=self.registry
        )
        
        self.task_processing_time = Histogram(
            'pulsepilot_task_processing_seconds',
            'Task processing time',
            ['task_type'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_connections = Gauge(
            'pulsepilot_db_connections_active',
            'Active database connections',
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            'pulsepilot_db_query_duration_seconds',
            'Database query duration',
            ['operation'],
            registry=self.registry
        )
        
        # Business metrics
        self.comments_processed = Counter(
            'pulsepilot_comments_processed_total',
            'Comments processed',
            ['platform', 'team_id'],
            registry=self.registry
        )
        
        self.replies_sent = Counter(
            'pulsepilot_replies_sent_total',
            'Replies sent to platforms',
            ['platform', 'team_id'],
            registry=self.registry
        )
        
        self.suggestions_generated = Counter(
            'pulsepilot_suggestions_generated_total',
            'AI suggestions generated',
            ['team_id'],
            registry=self.registry
        )
    
    def track_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        team_id: str = "unknown"
    ) -> None:
        """
        Track API request metrics
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            status_code: Response status code
            duration: Request duration in seconds
            team_id: Team identifier
        """
        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            team_id=team_id
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def track_llm_usage(
        self,
        model: str,
        operation: str,
        latency: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        team_id: str
    ) -> None:
        """
        Track LLM usage metrics
        
        Args:
            model: LLM model name
            operation: Operation type
            latency: Request latency in seconds
            prompt_tokens: Input tokens used
            completion_tokens: Output tokens used
            cost: Cost in USD
            team_id: Team identifier
        """
        self.llm_requests.labels(
            model=model,
            operation=operation,
            team_id=team_id
        ).inc()
        
        self.llm_latency.labels(
            model=model,
            operation=operation
        ).observe(latency)
        
        self.llm_tokens.labels(
            model=model,
            token_type="prompt",
            team_id=team_id
        ).inc(prompt_tokens)
        
        self.llm_tokens.labels(
            model=model,
            token_type="completion",
            team_id=team_id
        ).inc(completion_tokens)
        
        self.llm_cost.labels(
            model=model,
            team_id=team_id
        ).inc(cost)
    
    def track_platform_request(
        self,
        platform: str,
        operation: str,
        status: str
    ) -> None:
        """
        Track platform API request metrics
        
        Args:
            platform: Platform name
            operation: Operation type
            status: Request status
        """
        self.platform_requests.labels(
            platform=platform,
            operation=operation,
            status=status
        ).inc()
    
    def track_webhook_event(self, platform: str, status: str) -> None:
        """
        Track webhook event metrics
        
        Args:
            platform: Source platform
            status: Processing status
        """
        self.webhook_events.labels(
            platform=platform,
            status=status
        ).inc()
    
    def track_comment_processed(self, platform: str, team_id: str) -> None:
        """
        Track comment processing metrics
        
        Args:
            platform: Source platform
            team_id: Team identifier
        """
        self.comments_processed.labels(
            platform=platform,
            team_id=team_id
        ).inc()
    
    def track_reply_sent(self, platform: str, team_id: str) -> None:
        """
        Track reply submission metrics
        
        Args:
            platform: Target platform
            team_id: Team identifier
        """
        self.replies_sent.labels(
            platform=platform,
            team_id=team_id
        ).inc()
    
    def track_suggestion_generated(self, team_id: str) -> None:
        """
        Track AI suggestion generation metrics
        
        Args:
            team_id: Team identifier
        """
        self.suggestions_generated.labels(team_id=team_id).inc()
    
    def update_queue_size(self, queue_name: str, size: int) -> None:
        """
        Update task queue size metric
        
        Args:
            queue_name: Queue identifier
            size: Current queue size
        """
        self.task_queue_size.labels(queue_name=queue_name).set(size)
    
    def track_task_processing(self, task_type: str, duration: float) -> None:
        """
        Track background task processing metrics
        
        Args:
            task_type: Type of task
            duration: Processing duration in seconds
        """
        self.task_processing_time.labels(task_type=task_type).observe(duration)


# Global metrics collector
metrics = MetricsCollector()
