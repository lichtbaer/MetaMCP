"""
Security Middleware

This module provides security middleware for XSS protection, CSRF protection,
and input validation.
"""

import re
import secrets
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for XSS and CSRF protection."""

    def __init__(self, app, csrf_enabled: bool = True, xss_enabled: bool = True):
        super().__init__(app)
        self.csrf_enabled = csrf_enabled
        self.xss_enabled = xss_enabled
        self.csrf_tokens: dict[str, str] = {}  # In production, use Redis/database

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security checks."""
        try:
            # Skip security checks for certain paths
            if self._should_skip_security(request):
                return await call_next(request)

            # CSRF Protection
            if self.csrf_enabled and request.method in [
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
            ]:
                csrf_result = await self._check_csrf(request)
                if not csrf_result["valid"]:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "csrf_violation",
                            "message": "CSRF token validation failed",
                            "details": csrf_result["reason"],
                        },
                    )

            # XSS Protection
            if self.xss_enabled:
                xss_result = await self._check_xss(request)
                if not xss_result["valid"]:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "xss_violation",
                            "message": "XSS protection violation detected",
                            "details": xss_result["reason"],
                        },
                    )

            # Process request
            response = await call_next(request)

            # Add security headers
            self._add_security_headers(response)

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return await call_next(request)

    def _should_skip_security(self, request: Request) -> bool:
        """Check if security checks should be skipped for this request."""
        skip_paths = [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/mcp/ws",  # WebSocket connections
        ]

        return any(request.url.path.startswith(path) for path in skip_paths)

    async def _check_csrf(self, request: Request) -> dict[str, Any]:
        """Check CSRF token."""
        try:
            # Get CSRF token from header or form data
            csrf_token = request.headers.get("X-CSRF-Token")
            if not csrf_token:
                csrf_token = (await request.form()).get("csrf_token")

            if not csrf_token:
                return {"valid": False, "reason": "Missing CSRF token"}

            # Validate CSRF token
            if not self._validate_csrf_token(csrf_token):
                return {"valid": False, "reason": "Invalid CSRF token"}

            return {"valid": True, "reason": None}

        except Exception as e:
            logger.error(f"CSRF check error: {e}")
            return {"valid": False, "reason": f"CSRF validation error: {str(e)}"}

    def _validate_csrf_token(self, token: str) -> bool:
        """Validate CSRF token."""
        # In production, implement proper token validation
        # For now, check if token exists in our store
        return token in self.csrf_tokens.values()

    async def _check_xss(self, request: Request) -> dict[str, Any]:
        """Check for XSS attempts."""
        try:
            # Check URL parameters
            for param_name, param_value in request.query_params.items():
                if self._contains_xss_pattern(param_value):
                    return {
                        "valid": False,
                        "reason": f"XSS pattern detected in query parameter: {param_name}",
                    }

            # Check request body for JSON requests
            if request.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = await request.json()
                    if self._check_json_xss(body):
                        return {
                            "valid": False,
                            "reason": "XSS pattern detected in request body",
                        }
                except (ValueError, json.JSONDecodeError):
                    pass  # Skip if body is not valid JSON

            # Check form data
            if request.headers.get("content-type", "").startswith(
                "application/x-www-form-urlencoded"
            ):
                try:
                    form_data = await request.form()
                    for field_name, field_value in form_data.items():
                        if self._contains_xss_pattern(str(field_value)):
                            return {
                                "valid": False,
                                "reason": f"XSS pattern detected in form field: {field_name}",
                            }
                except Exception:
                    pass

            return {"valid": True, "reason": None}

        except Exception as e:
            logger.error(f"XSS check error: {e}")
            return {"valid": False, "reason": f"XSS validation error: {str(e)}"}

    def _contains_xss_pattern(self, value: str) -> bool:
        """Check if string contains XSS patterns."""
        if not isinstance(value, str):
            return False

        # Common XSS patterns
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<form[^>]*>",
            r"<input[^>]*>",
            r"<textarea[^>]*>",
            r"<select[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"<style[^>]*>",
            r"<base[^>]*>",
            r"<bgsound[^>]*>",
            r"<link[^>]*>",
            r"<xml[^>]*>",
            r"<xmp[^>]*>",
            r"<plaintext[^>]*>",
            r"<listing[^>]*>",
        ]

        value_lower = value.lower()
        for pattern in xss_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE | re.DOTALL):
                return True

        return False

    def _check_json_xss(self, data: Any) -> bool:
        """Recursively check JSON data for XSS patterns."""
        if isinstance(data, dict):
            for key, value in data.items():
                if self._check_json_xss(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._check_json_xss(item):
                    return True
        elif isinstance(data, str):
            return self._contains_xss_pattern(data)

        return False

    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        token = secrets.token_urlsafe(32)
        self.csrf_tokens[session_id] = token
        return token

    def invalidate_csrf_token(self, session_id: str) -> None:
        """Invalidate CSRF token for session."""
        if session_id in self.csrf_tokens:
            del self.csrf_tokens[session_id]
