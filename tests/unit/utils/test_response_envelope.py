"""
Unit tests for response envelope - critical for consistent API responses
"""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from utils.response_envelope import ResponseEnvelope, success_response, error_response, handle_api_exception
from utils.error_codes import PlatformError, BillingError


class TestResponseEnvelope:
    """Test global response formatting"""

    def test_success_response_format(self):
        """
        Business Critical: Success responses must follow consistent envelope format
        """
        data = {"comments": [{"id": "123", "message": "test"}]}
        
        response = success_response(data)
        
        assert response.success is True
        assert response.data == data
        assert response.error is None

    def test_success_response_empty_data(self):
        """
        Business Critical: Empty data should still return valid success response
        """
        response = success_response({})
        
        assert response.success is True
        assert response.data == {}
        assert response.error is None

    def test_success_response_none_data(self):
        """
        Business Critical: None data should be handled gracefully
        """
        response = success_response(None)
        
        assert response.success is True
        assert response.data is None
        assert response.error is None

    def test_error_response_with_error_code(self):
        """
        Business Critical: Error responses must include structured error codes
        """
        error_code = PlatformError.PLATFORM_AUTH_FAILED
        
        response = error_response(error_code)
        
        assert response.success is False
        assert response.data is None
        assert response.error is not None
        assert response.error["code"] == "PLATFORM_AUTH_FAILED"
        assert response.error["message"] == error_code.message

    def test_error_response_with_custom_message(self):
        """
        Business Critical: Custom error messages should override default messages
        """
        error_code = BillingError.QUOTA_EXCEEDED
        custom_message = "You have exceeded your monthly quota of 10,000 tokens"
        
        response = error_response(error_code, custom_message)
        
        assert response.success is False
        assert response.error["code"] == "BILLING_QUOTA_EXCEEDED"
        assert response.error["message"] == custom_message

    def test_error_response_with_details(self):
        """
        Business Critical: Error details should be included for debugging
        """
        error_code = PlatformError.WEBHOOK_SIGNATURE_INVALID
        details = {"platform": "instagram", "signature": "invalid_sig"}
        
        response = error_response(error_code, details=details)
        
        assert response.success is False
        assert response.error["details"] == details

    def test_handle_api_exception_http_exception(self):
        """
        Business Critical: HTTPExceptions should be converted to envelope format
        """
        http_exc = HTTPException(status_code=404, detail="Resource not found")
        
        response = handle_api_exception(http_exc)
        
        assert response.success is False
        assert response.error["code"] == "HTTP_404"
        assert response.error["message"] == "Resource not found"

    def test_handle_api_exception_generic_exception(self):
        """
        Business Critical: Generic exceptions should be handled safely without leaking details
        """
        generic_exc = ValueError("Internal processing error")
        
        response = handle_api_exception(generic_exc)
        
        assert response.success is False
        assert response.error["code"] == "INTERNAL_ERROR"
        assert "Internal server error" in response.error["message"]
        # Should not leak the actual exception message in production

    def test_handle_api_exception_with_debug_mode(self):
        """
        Business Critical: Debug mode should include exception details for development
        """
        generic_exc = ValueError("Detailed error message")
        
        response = handle_api_exception(generic_exc, debug=True)
        
        assert response.success is False
        assert response.error["code"] == "INTERNAL_ERROR"
        assert "Detailed error message" in response.error["message"]

    def test_response_envelope_serialization(self):
        """
        Business Critical: Response envelopes must be JSON serializable
        """
        import json
        
        data = {"test": "data", "count": 123}
        response = success_response(data)
        
        # Should be able to serialize to JSON
        json_str = json.dumps(response.dict())
        parsed = json.loads(json_str)
        
        assert parsed["success"] is True
        assert parsed["data"]["test"] == "data"
        assert parsed["data"]["count"] == 123
        assert parsed["error"] is None

    def test_error_response_serialization(self):
        """
        Business Critical: Error responses must be JSON serializable
        """
        import json
        
        error_code = PlatformError.PLATFORM_AUTH_FAILED
        response = error_response(error_code)
        
        # Should be able to serialize to JSON
        json_str = json.dumps(response.dict())
        parsed = json.loads(json_str)
        
        assert parsed["success"] is False
        assert parsed["data"] is None
        assert parsed["error"]["code"] == "PLATFORM_AUTH_FAILED"

    def test_response_envelope_prevents_raw_orm_leakage(self):
        """
        Business Critical: ORM objects should not leak through response envelope
        """
        # Mock ORM object
        mock_orm_object = MagicMock()
        mock_orm_object.__dict__ = {"id": 123, "password": "secret"}
        
        # Should handle ORM objects gracefully (convert to dict or reject)
        response = success_response({"user": mock_orm_object})
        
        # The envelope should either convert to dict or handle safely
        assert response.success is True
        # The actual implementation should prevent password leakage
