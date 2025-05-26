"""
Standard error code taxonomy
"""

from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes"""
    
    # Authentication & Authorization
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"
    
    # Platform Integration
    PLATFORM_AUTH_FAILED = "PLATFORM_AUTH_FAILED"
    PLATFORM_CONNECTION_FAILED = "PLATFORM_CONNECTION_FAILED"
    PLATFORM_WEBHOOK_INVALID = "PLATFORM_WEBHOOK_INVALID"
    PLATFORM_API_ERROR = "PLATFORM_API_ERROR"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    
    # Billing & Quotas
    BILLING_QUOTA_EXCEEDED = "BILLING_QUOTA_EXCEEDED"
    BILLING_PAYMENT_REQUIRED = "BILLING_PAYMENT_REQUIRED"
    BILLING_INVALID_SUBSCRIPTION = "BILLING_INVALID_SUBSCRIPTION"
    
    # Data Validation
    VALIDATION_INVALID_INPUT = "VALIDATION_INVALID_INPUT"
    VALIDATION_MISSING_FIELD = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    
    # Resource Management
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_ACCESS_DENIED = "RESOURCE_ACCESS_DENIED"
    
    # External Services
    EXTERNAL_SERVICE_UNAVAILABLE = "EXTERNAL_SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_TIMEOUT = "EXTERNAL_SERVICE_TIMEOUT"
    EXTERNAL_SERVICE_RATE_LIMITED = "EXTERNAL_SERVICE_RATE_LIMITED"
    
    # AI/ML Services
    AI_MODEL_ERROR = "AI_MODEL_ERROR"
    AI_CONTEXT_TOO_LARGE = "AI_CONTEXT_TOO_LARGE"
    AI_GENERATION_FAILED = "AI_GENERATION_FAILED"
    
    # System Errors
    SYSTEM_DATABASE_ERROR = "SYSTEM_DATABASE_ERROR"
    SYSTEM_CONFIGURATION_ERROR = "SYSTEM_CONFIGURATION_ERROR"
    SYSTEM_INTERNAL_ERROR = "SYSTEM_INTERNAL_ERROR"


ERROR_MESSAGES = {
    ErrorCode.AUTH_TOKEN_INVALID: "Authentication token is invalid",
    ErrorCode.AUTH_TOKEN_EXPIRED: "Authentication token has expired",
    ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS: "Insufficient permissions for this operation",
    
    ErrorCode.PLATFORM_AUTH_FAILED: "Platform authentication failed",
    ErrorCode.PLATFORM_CONNECTION_FAILED: "Failed to connect to platform",
    ErrorCode.PLATFORM_WEBHOOK_INVALID: "Invalid webhook signature or payload",
    ErrorCode.PLATFORM_API_ERROR: "Platform API returned an error",
    ErrorCode.PLATFORM_UNSUPPORTED: "Platform is not supported",
    
    ErrorCode.BILLING_QUOTA_EXCEEDED: "Usage quota has been exceeded",
    ErrorCode.BILLING_PAYMENT_REQUIRED: "Payment is required to continue",
    ErrorCode.BILLING_INVALID_SUBSCRIPTION: "Invalid or expired subscription",
    
    ErrorCode.VALIDATION_INVALID_INPUT: "Input validation failed",
    ErrorCode.VALIDATION_MISSING_FIELD: "Required field is missing",
    ErrorCode.VALIDATION_INVALID_FORMAT: "Invalid data format",
    
    ErrorCode.RESOURCE_NOT_FOUND: "Requested resource was not found",
    ErrorCode.RESOURCE_ALREADY_EXISTS: "Resource already exists",
    ErrorCode.RESOURCE_ACCESS_DENIED: "Access to resource is denied",
    
    ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE: "External service is unavailable",
    ErrorCode.EXTERNAL_SERVICE_TIMEOUT: "External service request timed out",
    ErrorCode.EXTERNAL_SERVICE_RATE_LIMITED: "External service rate limit exceeded",
    
    ErrorCode.AI_MODEL_ERROR: "AI model processing error",
    ErrorCode.AI_CONTEXT_TOO_LARGE: "AI context exceeds maximum size",
    ErrorCode.AI_GENERATION_FAILED: "AI content generation failed",
    
    ErrorCode.SYSTEM_DATABASE_ERROR: "Database operation failed",
    ErrorCode.SYSTEM_CONFIGURATION_ERROR: "System configuration error",
    ErrorCode.SYSTEM_INTERNAL_ERROR: "Internal system error"
}
