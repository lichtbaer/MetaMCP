"""
Configuration Management

This module provides centralized configuration management for the MetaMCP application
using Pydantic Settings for type-safe configuration with environment variable support.
"""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    """LLM Provider enumeration."""

    OPENAI = "openai"
    FALLBACK = "fallback"


class PolicyEngineType(Enum):
    OPA = "opa"
    INTERNAL = "internal"


class Settings(BaseSettings):
    """
    Application Settings

    Centralized configuration management using Pydantic Settings
    with environment variable support and validation.
    """

    # Application Settings
    app_name: str = Field(default="MetaMCP", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment")

    # Server Settings
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of workers")

    # Database Settings
    database_url: str = Field(
        default="postgresql://user:password@localhost/metamcp",
        description="Database connection URL",
    )
    database_pool_size: int = Field(default=10, description="Database pool size")
    database_max_overflow: int = Field(default=20, description="Database max overflow")

    # Vector Database Settings
    weaviate_url: str = Field(
        default="http://localhost:8080", description="Weaviate vector database URL"
    )
    weaviate_api_key: str | None = Field(default=None, description="Weaviate API key")
    vector_dimension: int = Field(default=1536, description="Vector dimension")

    # LLM Settings
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI, description="LLM provider"
    )
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4", description="OpenAI model")
    openai_base_url: str | None = Field(default=None, description="OpenAI base URL")
    openai_embedding_model: str = Field(
        default="text-embedding-ada-002", description="OpenAI embedding model"
    )

    # Authentication Settings
    secret_key: str = Field(
        default="",
        description="Secret key for JWT tokens (must be set in production)",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiry"
    )

    # Security Settings
    opa_url: str = Field(
        default="http://localhost:8181", description="Open Policy Agent URL"
    )
    opa_timeout: int = Field(default=5, description="OPA request timeout")

    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json, text)")

    # Monitoring Settings
    prometheus_metrics_port: int = Field(
        default=9090, description="Prometheus metrics port"
    )

    # OpenTelemetry Settings
    otlp_endpoint: str | None = Field(
        default=None, description="OTLP endpoint for telemetry"
    )
    otlp_insecure: bool = Field(
        default=True, description="Use insecure connection for OTLP"
    )
    telemetry_enabled: bool = Field(
        default=True, description="Enable OpenTelemetry telemetry"
    )

    # CORS Settings
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    cors_allow_credentials: bool = Field(
        default=True, description="Allow CORS credentials"
    )

    # Rate Limiting
    rate_limit_requests: int = Field(
        default=100, description="Rate limit requests per minute"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )
    rate_limit_use_redis: bool = Field(
        default=False, description="Use Redis backend for rate limiting"
    )
    rate_limit_redis_url: str = Field(
        default="redis://localhost:6379", description="Redis URL for rate limiting"
    )

    # Tool Execution Settings
    tool_timeout: int = Field(
        default=30, description="Timeout for tool execution in seconds"
    )
    tool_retry_attempts: int = Field(
        default=3, description="Number of retry attempts for tool execution"
    )
    tool_retry_delay: float = Field(
        default=1.0, description="Delay between retry attempts in seconds"
    )

    # Circuit Breaker Settings
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable circuit breaker pattern"
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, description="Number of failures before opening circuit"
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=60, description="Seconds to wait before trying half-open"
    )
    circuit_breaker_success_threshold: int = Field(
        default=2, description="Number of successes to close circuit again"
    )

    # Cache Configuration
    cache_enabled: bool = Field(default=True, description="Enable caching system")
    cache_redis_url: str = Field(
        default="redis://localhost:6379/1", description="Redis URL for caching"
    )
    cache_default_ttl: int = Field(
        default=3600, description="Default cache TTL in seconds"
    )
    cache_max_ttl: int = Field(
        default=604800, description="Maximum cache TTL in seconds (1 week)"
    )
    cache_max_connections: int = Field(
        default=20, description="Maximum Redis connections for cache"
    )

    # Performance Configuration
    database_pool_size: int = Field(
        default=10, description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=20, description="Database connection pool max overflow"
    )
    database_pool_timeout: int = Field(
        default=30, description="Database connection pool timeout"
    )
    database_pool_recycle: int = Field(
        default=3600, description="Database connection pool recycle time"
    )
    worker_threads: int = Field(
        default=4, description="Number of worker threads for background tasks"
    )
    max_concurrent_requests: int = Field(
        default=100, description="Maximum concurrent requests"
    )

    # Tool Registry Settings
    tool_registry_enabled: bool = Field(
        default=True, description="Enable tool registry"
    )
    tool_registry_auto_discovery: bool = Field(
        default=True, description="Auto-discover tools"
    )
    tool_registry_cache_ttl: int = Field(
        default=300, description="Tool registry cache TTL"
    )

    # Vector Search Settings
    vector_search_enabled: bool = Field(
        default=True, description="Enable vector search"
    )
    vector_search_similarity_threshold: float = Field(
        default=0.7, description="Vector search similarity threshold"
    )
    vector_search_max_results: int = Field(
        default=10, description="Max vector search results"
    )

    # Policy Settings
    policy_enforcement_enabled: bool = Field(
        default=True, description="Enable policy enforcement"
    )
    policy_default_allow: bool = Field(
        default=False, description="Default policy allow"
    )

    # Admin Settings
    admin_enabled: bool = Field(default=True, description="Enable admin interface")
    admin_port: int = Field(default=8501, description="Admin interface port")

    # Development Settings
    reload: bool = Field(default=False, description="Auto-reload on changes")
    docs_enabled: bool = Field(default=True, description="Enable API documentation")

    # OAuth Provider URLs (configurable via environment variables)
    google_oauth_authorization_url: str = Field(
        default="https://accounts.google.com/oauth/authorize",
        description="Google OAuth authorization URL",
    )
    google_oauth_token_url: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="Google OAuth token URL",
    )
    google_oauth_userinfo_url: str = Field(
        default="https://www.googleapis.com/oauth2/v2/userinfo",
        description="Google OAuth userinfo URL",
    )
    github_oauth_authorization_url: str = Field(
        default="https://github.com/login/oauth/authorize",
        description="GitHub OAuth authorization URL",
    )
    github_oauth_token_url: str = Field(
        default="https://github.com/login/oauth/access_token",
        description="GitHub OAuth token URL",
    )
    github_oauth_userinfo_url: str = Field(
        default="https://api.github.com/user", description="GitHub OAuth userinfo URL"
    )
    microsoft_oauth_authorization_url: str = Field(
        default="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        description="Microsoft OAuth authorization URL",
    )
    microsoft_oauth_token_url: str = Field(
        default="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        description="Microsoft OAuth token URL",
    )
    microsoft_oauth_userinfo_url: str = Field(
        default="https://graph.microsoft.com/v1.0/me",
        description="Microsoft OAuth userinfo URL",
    )

    # OAuth Provider Credentials
    google_oauth_client_id: str | None = Field(
        default=None, description="Google OAuth Client ID"
    )
    google_oauth_client_secret: str | None = Field(
        default=None, description="Google OAuth Client Secret"
    )
    github_oauth_client_id: str | None = Field(
        default=None, description="GitHub OAuth Client ID"
    )
    github_oauth_client_secret: str | None = Field(
        default=None, description="GitHub OAuth Client Secret"
    )
    microsoft_oauth_client_id: str | None = Field(
        default=None, description="Microsoft OAuth Client ID"
    )
    microsoft_oauth_client_secret: str | None = Field(
        default=None, description="Microsoft OAuth Client Secret"
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment setting."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level setting."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v):
        """Validate log format setting."""
        allowed = ["json", "text"]
        if v not in allowed:
            raise ValueError(f"Log format must be one of {allowed}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings: Application settings instance

    Note:
        Uses singleton pattern to ensure consistent settings across the application.
    """
    global _settings

    if _settings is None:
        _settings = Settings()

    return _settings


def reload_settings() -> Settings:
    """
    Reload application settings.

    Returns:
        Settings: Fresh settings instance

    Note:
        Useful for testing or when settings need to be refreshed.
    """
    global _settings
    _settings = Settings()
    return _settings


# Environment-specific settings
def get_environment_settings() -> dict[str, Any]:
    """
    Get environment-specific settings.

    Returns:
        Dict[str, Any]: Environment-specific configuration
    """
    settings = get_settings()

    if settings.environment == "development":
        return {
            "debug": True,
            "reload": True,
            "docs_enabled": True,
            "log_level": "DEBUG",
            "telemetry_enabled": False,
        }
    elif settings.environment == "staging":
        return {
            "debug": False,
            "reload": False,
            "docs_enabled": True,
            "log_level": "INFO",
            "telemetry_enabled": True,
        }
    elif settings.environment == "production":
        return {
            "debug": False,
            "reload": False,
            "docs_enabled": False,
            "log_level": "WARNING",
            "telemetry_enabled": True,
        }

    return {}


# Configuration validation
def validate_configuration() -> bool:
    """
    Validate application configuration.

    Returns:
        bool: True if configuration is valid

    Raises:
        ValueError: If configuration is invalid
    """
    try:
        settings = get_settings()

        # Validate required settings for production
        if settings.environment == "production":
            if not settings.secret_key:
                raise ValueError("Secret key must be set in production")

            if not settings.openai_api_key:
                raise ValueError("OpenAI API key must be configured")

        # Validate database URL
        if not settings.database_url:
            raise ValueError("Database URL must be configured")

        # Validate vector database settings
        if settings.vector_search_enabled and not settings.weaviate_url:
            raise ValueError("Weaviate URL must be configured for vector search")

        return True

    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")


# Configuration utilities
def get_config_path() -> Path:
    """
    Get configuration file path.

    Returns:
        Path: Path to configuration file
    """
    return Path.cwd() / ".env"


def create_env_template() -> str:
    """
    Create environment template.

    Returns:
        str: Environment template content
    """
    settings = Settings()
    template = []

    for field_name, field in settings.__fields__.items():
        if field.field_info.description:
            template.append(f"# {field.field_info.description}")
        template.append(f"{field_name.upper()}={field.default}")
        template.append("")

    return "\n".join(template)


# Export settings for convenience
__all__ = [
    "Settings",
    "get_settings",
    "reload_settings",
    "get_environment_settings",
    "validate_configuration",
    "get_config_path",
    "create_env_template",
]
