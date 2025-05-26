"""
Unit tests for error code taxonomy - critical for consistent error handling
"""

import pytest
from utils.error_codes import ErrorCode, PlatformError, BillingError, ValidationError as CustomValidationError


class TestErrorCodeTaxonomy:
    """Test structured error code system"""

    def test_platform_auth_failed_error_code(self):
        """
        Business Critical: Platform authentication failures must have consistent error codes
        """
        error = PlatformError.PLATFORM_AUTH_FAILED
        
        assert error.code == "PLATFORM_AUTH_FAILED"
        assert "authentication" in error.message.lower()
        assert error.status_code == 401

    def test_platform_webhook_invalid_error_code(self):
        """
        Business Critical: Invalid webhook signatures must have clear error codes
        """
        error = PlatformError.WEBHOOK_SIGNATURE_INVALID
        
        assert error.code == "WEBHOOK_SIGNATURE_INVALID"
        assert "signature" in error.message.lower()
        assert error.status_code == 401

    def test_billing_quota_exceeded_error_code(self):
        """
        Business Critical: Quota exceeded errors must be clearly identified for billing
        """
        error = BillingError.QUOTA_EXCEEDED
        
        assert error.code == "BILLING_QUOTA_EXCEEDED"
        assert "quota" in error.message.lower()
        assert error.status_code == 429

    def test_billing_payment_required_error_code(self):
        """
        Business Critical: Payment required errors must trigger billing flow
        """
        error = BillingError.PAYMENT_REQUIRED
        
        assert error.code == "BILLING_PAYMENT_REQUIRED"
        assert "payment" in error.message.lower()
        assert error.status_code == 402

    def test_validation_invalid_payload_error_code(self):
        """
        Business Critical: Invalid payloads must have structured validation errors
        """
        error = CustomValidationError.INVALID_PAYLOAD
        
        assert error.code == "VALIDATION_INVALID_PAYLOAD"
        assert "payload" in error.message.lower()
        assert error.status_code == 422

    def test_error_code_immutability(self):
        """
        Business Critical: Error codes must be immutable to prevent runtime changes
        """
        original_code = PlatformError.PLATFORM_AUTH_FAILED.code
        original_message = PlatformError.PLATFORM_AUTH_FAILED.message
        
        # Attempting to modify should not change the original
        error = PlatformError.PLATFORM_AUTH_FAILED
        
        assert error.code == original_code
        assert error.message == original_message

    def test_all_error_codes_have_required_fields(self):
        """
        Business Critical: All error codes must have code, message, and status_code
        """
        error_classes = [PlatformError, BillingError, CustomValidationError]
        
        for error_class in error_classes:
            for attr_name in dir(error_class):
                if not attr_name.startswith('_'):
                    error_code = getattr(error_class, attr_name)
                    if isinstance(error_code, ErrorCode):
                        assert hasattr(error_code, 'code')
                        assert hasattr(error_code, 'message')
                        assert hasattr(error_code, 'status_code')
                        assert error_code.code is not None
                        assert error_code.message is not None
                        assert isinstance(error_code.status_code, int)

    def test_error_codes_unique_within_class(self):
        """
        Business Critical: Error codes within each class must be unique
        """
        error_classes = [PlatformError, BillingError, CustomValidationError]
        
        for error_class in error_classes:
            codes = []
            for attr_name in dir(error_class):
                if not attr_name.startswith('_'):
                    error_code = getattr(error_class, attr_name)
                    if isinstance(error_code, ErrorCode):
                        codes.append(error_code.code)
            
            # All codes should be unique
            assert len(codes) == len(set(codes)), f"Duplicate error codes found in {error_class.__name__}"

    def test_status_codes_are_valid_http_codes(self):
        """
        Business Critical: All status codes must be valid HTTP status codes
        """
        valid_status_codes = {400, 401, 402, 403, 404, 409, 422, 429, 500, 502, 503}
        error_classes = [PlatformError, BillingError, CustomValidationError]
        
        for error_class in error_classes:
            for attr_name in dir(error_class):
                if not attr_name.startswith('_'):
                    error_code = getattr(error_class, attr_name)
                    if isinstance(error_code, ErrorCode):
                        assert error_code.status_code in valid_status_codes, \
                            f"Invalid status code {error_code.status_code} in {error_code.code}"
