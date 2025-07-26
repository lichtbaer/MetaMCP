"""
Tests for error handling functionality.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from metamcp.utils.error_handler import (
    ErrorContext,
    ErrorDetails,
    ErrorHandler,
    ErrorRecoveryHandler,
    get_error_stats,
    handle_request_error,
)


class TestErrorContext:
    """Test ErrorContext class."""

    def test_error_context_creation(self):
        """Test creating error context."""
        context = ErrorContext(
            correlation_id="test-123",
            timestamp=datetime.utcnow(),
            user_id="user123",
            request_id="req456",
        )

        assert context.correlation_id == "test-123"
        assert context.user_id == "user123"
        assert context.request_id == "req456"

    def test_error_context_defaults(self):
        """Test error context with defaults."""
        context = ErrorContext()

        assert context.correlation_id is not None
        assert context.timestamp is not None
        assert context.user_id is None
        assert context.request_id is None


class TestErrorDetails:
    """Test ErrorDetails class."""

    def test_error_details_creation(self):
        """Test creating error details."""
        context = ErrorContext()
        details = ErrorDetails(
            error_code="TEST_ERROR",
            message="Test error message",
            details={"key": "value"},
            context=context,
            severity="error",
            category="test",
            recoverable=True,
        )

        assert details.error_code == "TEST_ERROR"
        assert details.message == "Test error message"
        assert details.details == {"key": "value"}
        assert details.context == context
        assert details.severity == "error"
        assert details.category == "test"
        assert details.recoverable is True

    def test_error_details_defaults(self):
        """Test error details with defaults."""
        details = ErrorDetails(error_code="TEST_ERROR", message="Test error message")

        assert details.severity == "error"
        assert details.category == "general"
        assert details.recoverable is True
        assert details.retry_after is None


class TestErrorHandler:
    """Test ErrorHandler class."""

    @pytest.fixture
    def error_handler(self):
        """Create error handler for testing."""
        return ErrorHandler()

    def test_initialization(self, error_handler):
        """Test error handler initialization."""
        assert error_handler.error_reports == []
        assert error_handler.logger is not None

    def test_create_error_context(self, error_handler):
        """Test creating error context."""
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.url.path = "/api/test"
        request.method = "GET"

        context = error_handler.create_error_context(request, "user123")

        assert context.client_ip == "127.0.0.1"
        assert context.user_agent == "test-agent"
        assert context.endpoint == "/api/test"
        assert context.method == "GET"
        assert context.user_id == "user123"

    def test_create_error_context_no_request(self, error_handler):
        """Test creating error context without request."""
        context = error_handler.create_error_context(user_id="user123")

        assert context.user_id == "user123"
        assert context.client_ip is None
        assert context.user_agent is None

    def test_create_error_response(self, error_handler):
        """Test creating error response."""
        context = ErrorContext()
        error_details = ErrorDetails(
            error_code="TEST_ERROR",
            message="Test error",
            context=context,
            severity="error",
            category="test",
            recoverable=True,
        )

        response = error_handler.create_error_response(error_details)

        assert "error" in response
        assert response["error"]["code"] == "TEST_ERROR"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["severity"] == "error"
        assert response["error"]["category"] == "test"
        assert response["error"]["recoverable"] is True

    def test_handle_exception(self, error_handler):
        """Test handling an exception."""
        exception = ValueError("Test exception")
        context = ErrorContext()

        error_details = error_handler.handle_exception(exception, context)

        assert error_details.error_code == "GENERAL_ERROR"
        assert "Test exception" in error_details.message
        assert error_details.context == context
        assert error_details.severity == "error"
        assert error_details.category == "general"

    def test_handle_exception_without_context(self, error_handler):
        """Test handling exception without context."""
        exception = ValueError("Test exception")

        error_details = error_handler.handle_exception(exception)

        assert error_details.error_code == "GENERAL_ERROR"
        assert error_details.context is not None
        assert error_details.context.correlation_id is not None

    def test_classify_exception(self, error_handler):
        """Test exception classification."""
        # Test ValueError
        code, severity, category, recoverable = error_handler._classify_exception(
            ValueError("Test error")
        )
        assert code == "GENERAL_ERROR"
        assert category == "general"
        assert recoverable is True

        # Test ConnectionError
        code, severity, category, recoverable = error_handler._classify_exception(
            ConnectionError("Connection failed")
        )
        assert code == "NETWORK_ERROR"
        assert category == "network"
        assert recoverable is True

        # Test PermissionError
        code, severity, category, recoverable = error_handler._classify_exception(
            PermissionError("Access denied")
        )
        assert code == "PERMISSION_DENIED"
        assert category == "authorization"
        assert recoverable is False

    def test_get_error_statistics(self, error_handler):
        """Test getting error statistics."""
        # Handle some errors first
        exception1 = ValueError("Error 1")
        exception2 = ConnectionError("Error 2")

        error_handler.handle_exception(exception1)
        error_handler.handle_exception(exception2)

        stats = error_handler.get_error_statistics()

        assert "total_errors" in stats
        assert "by_category" in stats
        assert "by_severity" in stats
        assert stats["total_errors"] == 2
        assert stats["by_category"]["general"] == 1
        assert stats["by_category"]["network"] == 1

    def test_clear_error_reports(self, error_handler):
        """Test clearing error reports."""
        exception = ValueError("Test error")
        error_handler.handle_exception(exception)

        assert len(error_handler.error_reports) == 1

        error_handler.clear_error_reports()

        assert len(error_handler.error_reports) == 0


class TestErrorRecoveryHandler:
    """Test ErrorRecoveryHandler class."""

    @pytest.fixture
    def recovery_handler(self):
        """Create recovery handler for testing."""
        return ErrorRecoveryHandler()

    def test_should_retry(self, recovery_handler):
        """Test should retry logic."""
        context = ErrorContext()
        error_details = ErrorDetails(
            error_code="ConnectionError",
            message="Connection failed",
            context=context,
            recoverable=True,
        )

        # Should retry on first attempt
        assert recovery_handler.should_retry(error_details, 1) is True

        # Should not retry after max attempts
        assert recovery_handler.should_retry(error_details, 5) is False

        # Should not retry non-recoverable errors
        error_details.recoverable = False
        assert recovery_handler.should_retry(error_details, 1) is False

    def test_get_retry_delay(self, recovery_handler):
        """Test retry delay calculation."""
        # Exponential backoff
        delay1 = recovery_handler.get_retry_delay(1, base_delay=1.0)
        delay2 = recovery_handler.get_retry_delay(2, base_delay=1.0)
        delay3 = recovery_handler.get_retry_delay(3, base_delay=1.0)

        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0

    def test_create_retry_response(self, recovery_handler):
        """Test creating retry response."""
        context = ErrorContext()
        error_details = ErrorDetails(
            error_code="ConnectionError",
            message="Connection failed",
            context=context,
            recoverable=True,
        )

        response = recovery_handler.create_retry_response(error_details, 1)

        assert "error" in response
        assert "retry_after" in response["error"]
        assert response["error"]["retry_after"] == 1.0
        assert "attempt_count" in response["error"]
        assert response["error"]["attempt_count"] == 1


class TestErrorHandlingFunctions:
    """Test error handling utility functions."""

    def test_handle_request_error(self):
        """Test handle_request_error function."""
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.url.path = "/api/test"
        request.method = "GET"

        exception = ValueError("Test error")

        response = handle_request_error(exception, request, "user123")

        assert "error" in response
        assert response["error"]["code"] == "GENERAL_ERROR"
        assert "Test error" in response["error"]["message"]

    def test_handle_request_error_no_request(self):
        """Test handle_request_error without request."""
        exception = ValueError("Test error")

        response = handle_request_error(exception)

        assert "error" in response
        assert response["error"]["code"] == "GENERAL_ERROR"

    def test_get_error_stats(self):
        """Test get_error_stats function."""
        stats = get_error_stats()

        assert isinstance(stats, dict)
        assert "total_errors" in stats
        assert "by_category" in stats
        assert "by_severity" in stats


class TestErrorHandlingIntegration:
    """Test error handling integration scenarios."""

    def test_complete_error_handling_flow(self):
        """Test complete error handling flow."""
        handler = ErrorHandler()
        recovery_handler = ErrorRecoveryHandler()

        # Create request
        request = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.url.path = "/api/test"
        request.method = "GET"

        # Handle an error
        exception = ConnectionError("Connection failed")
        context = handler.create_error_context(request, "user123")
        error_details = handler.handle_exception(exception, context)

        # Verify error details
        assert error_details.error_code == "NETWORK_ERROR"
        assert error_details.context == context
        assert error_details.recoverable is True
        assert error_details.category == "network"

        # Test recovery
        should_retry = recovery_handler.should_retry(error_details, 1)
        assert should_retry is True

        retry_delay = recovery_handler.get_retry_delay(1)
        assert retry_delay == 1.0

        retry_response = recovery_handler.create_retry_response(error_details, 1)
        assert "retry_after" in retry_response["error"]

        # Verify statistics
        stats = handler.get_error_statistics()
        assert stats["total_errors"] == 1
        assert stats["by_category"]["network"] == 1

    def test_error_classification_integration(self):
        """Test error classification integration."""
        handler = ErrorHandler()

        # Test different exception types
        exceptions = [
            (ValueError("Test error"), "general"),
            (ConnectionError("Connection failed"), "network"),
            (PermissionError("Access denied"), "authorization"),
            (TimeoutError("Request timeout"), "network"),
            (KeyError("Missing key"), "general"),
        ]

        for exception, expected_category in exceptions:
            error_details = handler.handle_exception(exception)
            assert error_details.category == expected_category

    def test_error_response_integration(self):
        """Test error response integration."""
        handler = ErrorHandler()

        # Create error
        exception = ValueError("Test error")
        context = ErrorContext(user_id="user123")
        error_details = handler.handle_exception(exception, context)

        # Create response
        response = handler.create_error_response(error_details)

        # Verify response structure
        assert "error" in response
        assert response["error"]["code"] == "GENERAL_ERROR"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["severity"] == "error"
        assert response["error"]["category"] == "general"
        assert response["error"]["recoverable"] is True
        assert "correlation_id" in response["error"]
        assert "timestamp" in response["error"]

    def test_error_recovery_integration(self):
        """Test error recovery integration."""
        recovery_handler = ErrorRecoveryHandler()

        # Test recoverable error
        context = ErrorContext()
        recoverable_error = ErrorDetails(
            error_code="NETWORK_ERROR",
            message="Connection failed",
            context=context,
            category="network",
            recoverable=True,
        )

        # Should retry on first two attempts
        for attempt in range(1, 3):
            should_retry = recovery_handler.should_retry(recoverable_error, attempt)
            assert should_retry is True

            delay = recovery_handler.get_retry_delay(attempt)
            assert delay == 1.0 * (2 ** (attempt - 1))  # Exponential backoff

            response = recovery_handler.create_retry_response(
                recoverable_error, attempt
            )
            assert response["error"]["retry_after"] == delay
            assert response["error"]["attempt_count"] == attempt

        # Should not retry on third attempt (max attempts reached)
        should_retry = recovery_handler.should_retry(recoverable_error, 3)
        assert should_retry is False

        # Should not retry after max attempts
        should_retry = recovery_handler.should_retry(recoverable_error, 5)
        assert should_retry is False

        # Test non-recoverable error
        non_recoverable_error = ErrorDetails(
            error_code="PermissionError",
            message="Access denied",
            context=context,
            recoverable=False,
        )

        should_retry = recovery_handler.should_retry(non_recoverable_error, 1)
        assert should_retry is False
