"""
OAuth Authentication Module

This module provides OAuth 2.0 authentication support for both users and AI agents,
with specific handling for FastMCP agent authentication flows.
"""

import json
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ..config import get_settings
from ..exceptions import MetaMCPException
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class OAuthProvider(BaseModel):
    """OAuth provider configuration."""

    name: str = Field(..., description="Provider name")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    authorization_url: str = Field(..., description="Authorization endpoint")
    token_url: str = Field(..., description="Token endpoint")
    userinfo_url: str | None = Field(None, description="User info endpoint")
    scopes: list[str] = Field(default=["openid", "email", "profile"])
    redirect_uri: str = Field(..., description="Redirect URI")

    model_config = {"extra": "forbid"}


class OAuthToken(BaseModel):
    """OAuth token model."""

    access_token: str = Field(..., description="Access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int | None = Field(None, description="Token expiry in seconds")
    refresh_token: str | None = Field(None, description="Refresh token")
    scope: str | None = Field(None, description="Token scope")
    expires_at: datetime | None = Field(None, description="Token expiry timestamp")

    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at


class OAuthUser(BaseModel):
    """OAuth user model."""

    provider: str = Field(..., description="OAuth provider")
    provider_user_id: str = Field(..., description="Provider user ID")
    email: str | None = Field(None, description="User email")
    name: str | None = Field(None, description="User name")
    picture: str | None = Field(None, description="User picture URL")
    scopes: list[str] = Field(default_factory=list, description="Granted scopes")
    is_agent: bool = Field(default=False, description="Whether user is an AI agent")


class OAuthManager:
    """
    OAuth authentication manager for users and AI agents.

    Supports multiple OAuth providers and handles both user and agent authentication
    flows, with specific optimizations for FastMCP agent authentication.
    """

    def __init__(self):
        """Initialize OAuth manager."""
        self.settings = settings
        self.providers: dict[str, OAuthProvider] = {}
        self.state_store: dict[str, dict[str, Any]] = {}
        self.token_store: dict[str, OAuthToken] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize OAuth manager with configured providers."""
        try:
            logger.info("Initializing OAuth Manager...")

            # Load OAuth providers from configuration
            await self._load_providers()

            # Initialize state management
            await self._initialize_state_management()

            self._initialized = True
            logger.info("OAuth Manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize OAuth Manager: {e}")
            raise

    async def _load_providers(self) -> None:
        """Load OAuth providers from configuration."""
        # Determine protocol based on environment
        protocol = "https" if self.settings.environment == "production" else "http"
        base_url = f"{protocol}://{self.settings.host}:{self.settings.port}"

        # Google OAuth
        if (
            self.settings.google_oauth_client_id
            and self.settings.google_oauth_client_secret
        ):
            self.providers["google"] = OAuthProvider(
                name="google",
                client_id=self.settings.google_oauth_client_id,
                client_secret=self.settings.google_oauth_client_secret,
                authorization_url=self.settings.google_oauth_authorization_url,
                token_url=self.settings.google_oauth_token_url,
                userinfo_url=self.settings.google_oauth_userinfo_url,
                scopes=["openid", "email", "profile"],
                redirect_uri=f"{base_url}/api/v1/oauth/callback/google",
            )
            logger.info("Google OAuth provider configured")

        # GitHub OAuth
        if (
            self.settings.github_oauth_client_id
            and self.settings.github_oauth_client_secret
        ):
            self.providers["github"] = OAuthProvider(
                name="github",
                client_id=self.settings.github_oauth_client_id,
                client_secret=self.settings.github_oauth_client_secret,
                authorization_url=self.settings.github_oauth_authorization_url,
                token_url=self.settings.github_oauth_token_url,
                userinfo_url=self.settings.github_oauth_userinfo_url,
                scopes=["read:user", "user:email"],
                redirect_uri=f"{base_url}/api/v1/oauth/callback/github",
            )
            logger.info("GitHub OAuth provider configured")

        # Microsoft OAuth
        if (
            self.settings.microsoft_oauth_client_id
            and self.settings.microsoft_oauth_client_secret
        ):
            self.providers["microsoft"] = OAuthProvider(
                name="microsoft",
                client_id=self.settings.microsoft_oauth_client_id,
                client_secret=self.settings.microsoft_oauth_client_secret,
                authorization_url=self.settings.microsoft_oauth_authorization_url,
                token_url=self.settings.microsoft_oauth_token_url,
                userinfo_url=self.settings.microsoft_oauth_userinfo_url,
                scopes=["openid", "profile", "email"],
                redirect_uri=f"{base_url}/api/v1/oauth/callback/microsoft",
            )
            logger.info("Microsoft OAuth provider configured")

        logger.info(
            f"Loaded {len(self.providers)} OAuth providers: {list(self.providers.keys())}"
        )

    async def _initialize_state_management(self) -> None:
        """Initialize OAuth state management."""
        # In production, use Redis or database for state storage
        self.state_store = {}

    def get_authorization_url(
        self,
        provider: str,
        is_agent: bool = False,
        agent_id: str | None = None,
        requested_scopes: list[str] | None = None,
    ) -> str:
        """
        Get OAuth authorization URL.

        Args:
            provider: OAuth provider name
            is_agent: Whether this is an agent authentication
            agent_id: Agent ID for agent-specific flows
            requested_scopes: Requested OAuth scopes

        Returns:
            Authorization URL

        Raises:
            MetaMCPException: If provider not found or invalid configuration
        """
        if provider not in self.providers:
            raise MetaMCPException(
                error_code="oauth_provider_not_found",
                message=f"OAuth provider '{provider}' not configured",
                details={"available_providers": list(self.providers.keys())},
            )

        oauth_provider = self.providers[provider]

        # Generate state parameter
        state = secrets.token_urlsafe(32)

        # Store state with additional context
        self.state_store[state] = {
            "provider": provider,
            "is_agent": is_agent,
            "agent_id": agent_id,
            "requested_scopes": requested_scopes or oauth_provider.scopes,
            "created_at": datetime.utcnow(),
        }

        # Build authorization URL
        params = {
            "client_id": oauth_provider.client_id,
            "redirect_uri": oauth_provider.redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": " ".join(requested_scopes or oauth_provider.scopes),
        }

        # Add agent-specific parameters
        if is_agent:
            params["prompt"] = "consent"
            params["access_type"] = "offline"

        authorization_url = f"{oauth_provider.authorization_url}?{urlencode(params)}"

        logger.info(f"Generated authorization URL for {provider} (agent: {is_agent})")
        return authorization_url

    async def handle_callback(
        self, provider: str, code: str, state: str, error: str | None = None
    ) -> OAuthUser:
        """
        Handle OAuth callback and exchange code for tokens.

        Args:
            provider: OAuth provider name
            code: Authorization code
            state: State parameter
            error: OAuth error if any

        Returns:
            OAuth user information

        Raises:
            MetaMCPException: If callback handling fails
        """
        if error:
            raise MetaMCPException(
                error_code="oauth_authorization_failed",
                message=f"OAuth authorization failed: {error}",
                details={"provider": provider, "error": error},
            )

        # Validate state
        if state not in self.state_store:
            raise MetaMCPException(
                error_code="oauth_invalid_state",
                message="Invalid OAuth state parameter",
                details={"state": state},
            )

        state_data = self.state_store[state]
        is_agent = state_data.get("is_agent", False)
        agent_id = state_data.get("agent_id")

        try:
            # Exchange code for tokens
            token = await self._exchange_code_for_token(provider, code, state)

            # Get user information
            user_info = await self._get_user_info(provider, token)

            # Create OAuth user
            oauth_user = OAuthUser(
                provider=provider,
                provider_user_id=user_info.get("id") or user_info.get("sub"),
                email=user_info.get("email"),
                name=user_info.get("name"),
                picture=user_info.get("picture"),
                scopes=state_data.get("requested_scopes", []),
                is_agent=is_agent,
            )

            # Store token for agent sessions
            if is_agent and agent_id:
                await self._store_agent_token(agent_id, provider, token)
                logger.info(f"Stored OAuth token for agent {agent_id} ({provider})")

            # Clean up state
            del self.state_store[state]

            logger.info(f"OAuth callback completed for {provider} (agent: {is_agent})")
            return oauth_user

        except Exception as e:
            logger.error(f"OAuth callback failed for {provider}: {e}")
            raise MetaMCPException(
                error_code="oauth_callback_failed",
                message="OAuth callback processing failed",
                details={"provider": provider, "error": str(e)},
            )

    async def _exchange_code_for_token(
        self, provider: str, code: str, state: str
    ) -> OAuthToken:
        """Exchange authorization code for access token."""
        oauth_provider = self.providers[provider]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                oauth_provider.token_url,
                data={
                    "client_id": oauth_provider.client_id,
                    "client_secret": oauth_provider.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": oauth_provider.redirect_uri,
                    "state": state,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                raise MetaMCPException(
                    error_code="oauth_token_exchange_failed",
                    message="Failed to exchange code for token",
                    details={
                        "provider": provider,
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )

            token_data = response.json()

            # Calculate expiry
            expires_at = None
            if token_data.get("expires_in"):
                expires_at = datetime.utcnow() + timedelta(
                    seconds=token_data["expires_in"]
                )

            return OAuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token"),
                scope=token_data.get("scope"),
                expires_at=expires_at,
            )

    async def _get_user_info(self, provider: str, token: OAuthToken) -> dict[str, Any]:
        """Get user information from OAuth provider."""
        oauth_provider = self.providers[provider]

        if not oauth_provider.userinfo_url:
            # For providers without userinfo endpoint, decode JWT token
            return await self._decode_jwt_token(token.access_token)

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"{token.token_type} {token.access_token}"}

            if provider == "github":
                headers["Accept"] = "application/vnd.github.v3+json"

            response = await client.get(oauth_provider.userinfo_url, headers=headers)

            if response.status_code != 200:
                raise MetaMCPException(
                    error_code="oauth_userinfo_failed",
                    message="Failed to get user information",
                    details={
                        "provider": provider,
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )

            return response.json()

    async def _decode_jwt_token(self, token: str) -> dict[str, Any]:
        """Decode JWT token to extract user information."""
        # Simple JWT decoding for demo purposes
        # In production, use proper JWT library with signature verification
        try:
            import base64

            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT token format")

            payload = parts[1]
            # Add padding if needed
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded.decode("utf-8"))

        except Exception as e:
            logger.error(f"Failed to decode JWT token: {e}")
            return {"sub": "unknown", "email": "unknown@example.com"}

    async def _store_agent_token(
        self, agent_id: str, provider: str, token: OAuthToken
    ) -> None:
        """Store OAuth token for agent sessions."""
        # In production, use secure token storage (e.g., encrypted database)
        token_key = f"agent:{agent_id}:{provider}"
        self.token_store[token_key] = token

        logger.info(f"Stored OAuth token for agent {agent_id} ({provider})")

    async def get_agent_token(self, agent_id: str, provider: str) -> OAuthToken | None:
        """Get stored OAuth token for agent."""
        token_key = f"agent:{agent_id}:{provider}"
        token = self.token_store.get(token_key)

        if token and token.is_expired():
            # Try to refresh token
            refreshed_token = await self._refresh_token(provider, token)
            if refreshed_token:
                self.token_store[token_key] = refreshed_token
                return refreshed_token
            else:
                # Remove expired token
                del self.token_store[token_key]
                return None

        return token

    async def _refresh_token(
        self, provider: str, token: OAuthToken
    ) -> OAuthToken | None:
        """Refresh OAuth token."""
        if not token.refresh_token:
            return None

        oauth_provider = self.providers[provider]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    oauth_provider.token_url,
                    data={
                        "client_id": oauth_provider.client_id,
                        "client_secret": oauth_provider.client_secret,
                        "refresh_token": token.refresh_token,
                        "grant_type": "refresh_token",
                    },
                    headers={"Accept": "application/json"},
                )

                if response.status_code != 200:
                    return None

                token_data = response.json()

                # Calculate expiry
                expires_at = None
                if token_data.get("expires_in"):
                    expires_at = datetime.utcnow() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                return OAuthToken(
                    access_token=token_data["access_token"],
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_in=token_data.get("expires_in"),
                    refresh_token=token_data.get("refresh_token", token.refresh_token),
                    scope=token_data.get("scope"),
                    expires_at=expires_at,
                )

        except Exception as e:
            logger.error(f"Failed to refresh token for {provider}: {e}")
            return None

    async def validate_agent_session(self, agent_id: str, provider: str) -> bool:
        """Validate agent OAuth session."""
        token = await self.get_agent_token(agent_id, provider)
        return token is not None and not token.is_expired()

    async def revoke_agent_session(self, agent_id: str, provider: str) -> None:
        """Revoke agent OAuth session."""
        token_key = f"agent:{agent_id}:{provider}"
        if token_key in self.token_store:
            del self.token_store[token_key]
            logger.info(f"Revoked OAuth session for agent {agent_id} ({provider})")

    async def get_fastmcp_agent_token(
        self, agent_id: str, provider: str
    ) -> dict[str, Any] | None:
        """
        Get OAuth token for FastMCP agent with automatic refresh.

        Args:
            agent_id: FastMCP agent ID
            provider: OAuth provider name

        Returns:
            Token information for FastMCP agent or None if not available
        """
        token = await self.get_agent_token(agent_id, provider)
        if not token:
            return None

        return {
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_in": token.expires_in,
            "scope": token.scope,
            "provider": provider,
            "agent_id": agent_id,
        }

    def get_available_providers(self) -> list[str]:
        """Get list of available OAuth providers."""
        return list(self.providers.keys())

    @property
    def is_initialized(self) -> bool:
        """Check if OAuth manager is initialized."""
        return self._initialized


# Global OAuth manager instance
_oauth_manager: OAuthManager | None = None


def get_oauth_manager() -> OAuthManager:
    """Get global OAuth manager instance."""
    global _oauth_manager

    if _oauth_manager is None:
        _oauth_manager = OAuthManager()

    return _oauth_manager
