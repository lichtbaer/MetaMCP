"""
Health Check API Router

This module provides health check endpoints for monitoring the
MCP Meta-Server status and component health.
"""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Create router
health_router = APIRouter()

# Server start time for uptime calculation
_server_start_time = time.time()


# =============================================================================
# Pydantic Models
# =============================================================================


class HealthStatus(BaseModel):
    """Health status response model."""

    healthy: bool
    timestamp: str
    version: str
    uptime: float | None = None
    error: str | None = None


class ComponentHealth(BaseModel):
    """Component health status model."""

    name: str
    status: str
    response_time: float | None = None
    error: str | None = None
    message: str | None = None
    details: dict | None = None


class DetailedHealthStatus(BaseModel):
    """Detailed health status response model."""

    overall_healthy: bool
    timestamp: str
    version: str
    uptime: float
    components: list[ComponentHealth]


# =============================================================================
# Health Check Functions
# =============================================================================


def get_uptime() -> float:
    """Calculate server uptime in seconds."""
    return time.time() - _server_start_time


def format_uptime(seconds: float) -> str:
    """Format uptime in human readable format."""
    if seconds < 0:
        return f"{int(seconds)}s"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


async def check_database_health() -> ComponentHealth:
    """Check database connectivity."""
    start_time = time.time()

    try:
        # Implement actual database health check
        from metamcp.config import get_settings

        settings = get_settings()

        # Check if database URL is configured
        if not settings.database_url:
            return ComponentHealth(
                name="database",
                status="unhealthy",
                message="Database URL not configured",
                response_time=time.time() - start_time,
                details={"error": "DATABASE_URL environment variable not set"},
            )

        # Use database manager for health check
        try:
            from metamcp.utils.database import get_database_manager

            db_manager = get_database_manager()

            if not db_manager.is_initialized:
                # Try to initialize if not already done
                await db_manager.initialize()

            # Use database manager health check
            health_result = await db_manager.health_check()

            if health_result["status"] == "healthy":
                return ComponentHealth(
                    name="database",
                    status="healthy",
                    response_time=health_result["response_time"],
                    details={
                        "connection": "successful",
                        "pool_stats": health_result["pool_stats"],
                        "query_result": health_result["test_query_result"],
                    },
                )
            else:
                return ComponentHealth(
                    name="database",
                    status="unhealthy",
                    message=f"Database health check failed: {health_result.get('error')}",
                    response_time=time.time() - start_time,
                    details={
                        "error": health_result.get("error"),
                        "database_url_configured": True,
                    },
                )

        except Exception as db_error:
            return ComponentHealth(
                name="database",
                status="unhealthy",
                message=f"Database connection failed: {str(db_error)}",
                response_time=time.time() - start_time,
                details={"error": str(db_error), "database_url_configured": True},
            )

    except Exception as e:
        return ComponentHealth(
            name="database",
            status="unhealthy",
            response_time=time.time() - start_time,
            error=str(e),
        )


async def check_vector_db_health() -> ComponentHealth:
    """Check vector database connectivity."""
    start_time = time.time()

    try:
        # Implement actual vector database health check
        from metamcp.config import get_settings

        settings = get_settings()

        # Check if Weaviate URL is configured
        if not settings.weaviate_url:
            return ComponentHealth(
                name="vector_db",
                status="unhealthy",
                message="Weaviate URL not configured",
                response_time=time.time() - start_time,
                details={"error": "WEAVIATE_URL environment variable not set"},
            )

        # Try to connect to Weaviate and check health
        try:
            # Parse the URL to get host and port
            from urllib.parse import urlparse

            import weaviate

            parsed_url = urlparse(settings.weaviate_url)
            host = parsed_url.hostname
            port = parsed_url.port or 80
            secure = parsed_url.scheme == "https"

            # Connect to Weaviate using the proper method
            client = weaviate.connect_to_custom(
                http_host=host,
                http_port=port,
                http_secure=secure,
                grpc_host=host,
                grpc_port=port,
                grpc_secure=secure,
            )

            # Check if Weaviate is ready
            is_ready = client.is_ready()
            response_time = time.time() - start_time

            if is_ready:
                # Get meta information
                meta_data = client.get_meta()
                return ComponentHealth(
                    name="vector_db",
                    status="healthy",
                    response_time=response_time,
                    details={
                        "ready": True,
                        "live": True,
                        "weaviate_url": settings.weaviate_url,
                        "version": getattr(meta_data, "version", "unknown"),
                        "hostname": host,
                    },
                )
            else:
                return ComponentHealth(
                    name="vector_db",
                    status="unhealthy",
                    message="Weaviate is not ready",
                    response_time=response_time,
                    details={
                        "error": "Not ready",
                        "weaviate_url": settings.weaviate_url,
                    },
                )

        except Exception as weaviate_error:
            return ComponentHealth(
                name="vector_db",
                status="unhealthy",
                message=f"Weaviate connection failed: {str(weaviate_error)}",
                response_time=time.time() - start_time,
                details={"error": str(weaviate_error), "weaviate_url_configured": True},
            )
    except Exception as e:
        return ComponentHealth(
            name="vector_db",
            status="unhealthy",
            response_time=time.time() - start_time,
            error=str(e),
        )


async def check_llm_service_health() -> ComponentHealth:
    """Check LLM service connectivity."""
    start_time = time.time()

    try:
        # Implement actual LLM service health check
        from metamcp.config import get_settings

        settings = get_settings()

        # Check configured LLM provider
        llm_provider = getattr(settings, "llm_provider", "openai").lower()

        if llm_provider == "openai":
            # Check OpenAI API key and connectivity
            openai_api_key = getattr(settings, "openai_api_key", None)
            if not openai_api_key:
                return ComponentHealth(
                    name="llm_service",
                    status="unhealthy",
                    message="OpenAI API key not configured",
                    response_time=time.time() - start_time,
                    details={
                        "error": "OPENAI_API_KEY environment variable not set",
                        "provider": "openai",
                    },
                )

            try:
                import openai

                # Simple API call to check connectivity
                client = openai.OpenAI(api_key=openai_api_key)
                # List models as a health check
                models = client.models.list()

                response_time = time.time() - start_time
                return ComponentHealth(
                    name="llm_service",
                    status="healthy",
                    response_time=response_time,
                    details={
                        "provider": "openai",
                        "api_key_configured": True,
                        "models_accessible": (
                            len(models.data) if hasattr(models, "data") else 0
                        ),
                    },
                )

            except Exception as openai_error:
                return ComponentHealth(
                    name="llm_service",
                    status="unhealthy",
                    message=f"OpenAI API connection failed: {str(openai_error)}",
                    response_time=time.time() - start_time,
                    details={"error": str(openai_error), "provider": "openai"},
                )

        elif llm_provider == "anthropic":
            # Check Anthropic API key
            anthropic_api_key = getattr(settings, "anthropic_api_key", None)
            if not anthropic_api_key:
                return ComponentHealth(
                    name="llm_service",
                    status="unhealthy",
                    message="Anthropic API key not configured",
                    response_time=time.time() - start_time,
                    details={
                        "error": "ANTHROPIC_API_KEY environment variable not set",
                        "provider": "anthropic",
                    },
                )

            try:
                import anthropic

                client = anthropic.Anthropic(api_key=anthropic_api_key)
                # Simple API call to check connectivity
                # Note: Anthropic doesn't have a models list endpoint, so we'll just validate the client
                response_time = time.time() - start_time
                return ComponentHealth(
                    name="llm_service",
                    status="healthy",
                    response_time=response_time,
                    details={
                        "provider": "anthropic",
                        "api_key_configured": True,
                        "client_initialized": True,
                    },
                )

            except Exception as anthropic_error:
                return ComponentHealth(
                    name="llm_service",
                    status="unhealthy",
                    message=f"Anthropic API connection failed: {str(anthropic_error)}",
                    response_time=time.time() - start_time,
                    details={"error": str(anthropic_error), "provider": "anthropic"},
                )
        else:
            # Unknown or unsupported provider
            return ComponentHealth(
                name="llm_service",
                status="unhealthy",
                message=f"Unsupported LLM provider: {llm_provider}",
                response_time=time.time() - start_time,
                details={
                    "error": f"Provider '{llm_provider}' not supported",
                    "supported_providers": ["openai", "anthropic"],
                },
            )
    except Exception as e:
        return ComponentHealth(
            name="llm_service",
            status="unhealthy",
            response_time=time.time() - start_time,
            error=str(e),
        )


# =============================================================================
# Dependencies
# =============================================================================


async def get_mcp_server():
    """Get MCP server instance from FastAPI app state."""
    # This will be injected by the main application
    pass


# =============================================================================
# API Endpoints
# =============================================================================


@health_router.get("/", response_model=HealthStatus, summary="Basic health check")
async def health_check():
    """
    Basic health check endpoint.

    Returns basic health status of the server.
    """
    try:
        uptime_seconds = get_uptime()

        return HealthStatus(
            healthy=True,
            timestamp=datetime.now(UTC).isoformat(),
            version="1.0.0",
            uptime=uptime_seconds,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthStatus(
            healthy=False,
            timestamp=datetime.now(UTC).isoformat(),
            version="1.0.0",
            error=str(e),
        )


@health_router.get(
    "/detailed", response_model=DetailedHealthStatus, summary="Detailed health check"
)
async def detailed_health_check():
    """
    Detailed health check endpoint.

    Returns detailed health status of all components.
    """
    try:
        # Check all components
        components = []

        # Database health
        db_health = await check_database_health()
        components.append(db_health)

        # Vector database health
        vector_health = await check_vector_db_health()
        components.append(vector_health)

        # LLM service health
        llm_health = await check_llm_service_health()
        components.append(llm_health)

        # Determine overall health
        overall_healthy = all(comp.status == "healthy" for comp in components)
        uptime_seconds = get_uptime()

        return DetailedHealthStatus(
            overall_healthy=overall_healthy,
            timestamp=datetime.now(UTC).isoformat(),
            version="1.0.0",
            uptime=uptime_seconds,
            components=components,
        )

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@health_router.get("/ready", summary="Readiness probe")
async def readiness_probe():
    """
    Readiness probe endpoint.

    Returns 200 if the service is ready to accept requests.
    """
    try:
        # Check if all critical components are ready
        db_health = await check_database_health()
        vector_health = await check_vector_db_health()

        if db_health.status != "healthy" or vector_health.status != "healthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready",
            )

        return {"status": "ready"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(e)}",
        )


@health_router.get("/live", summary="Liveness probe")
async def liveness_probe():
    """
    Liveness probe endpoint.

    Returns 200 if the service is alive and responsive.
    """
    try:
        # Simple liveness check - just verify the service is responding
        uptime_seconds = get_uptime()

        return {
            "status": "alive",
            "uptime": uptime_seconds,
            "uptime_formatted": format_uptime(uptime_seconds),
        }

    except Exception as e:
        logger.error(f"Liveness probe failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not alive: {str(e)}",
        )


@health_router.get("/info", summary="Service information")
async def service_info():
    """
    Get service information.

    Returns detailed information about the service.
    """
    try:
        uptime_seconds = get_uptime()

        return {
            "service": "MetaMCP",
            "version": "1.0.0",
            "uptime": uptime_seconds,
            "uptime_formatted": format_uptime(uptime_seconds),
            "start_time": datetime.fromtimestamp(_server_start_time, UTC).isoformat(),
            "current_time": datetime.now(UTC).isoformat(),
            "environment": settings.environment,
            "debug": settings.debug,
        }

    except Exception as e:
        logger.error(f"Service info failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service info: {str(e)}",
        )


@health_router.get("/circuit-breakers", summary="Circuit breaker status")
async def circuit_breaker_status():
    """Get circuit breaker status and statistics."""
    try:
        from ..utils.circuit_breaker import get_circuit_breaker_manager

        manager = get_circuit_breaker_manager()
        stats = await manager.get_all_stats()

        return {
            "circuit_breakers": {
                name: {
                    "state": stat.current_state.value,
                    "total_calls": stat.total_calls,
                    "successful_calls": stat.successful_calls,
                    "failed_calls": stat.failed_calls,
                    "last_failure_time": stat.last_failure_time,
                    "last_success_time": stat.last_success_time,
                }
                for name, stat in stats.items()
            },
            "total_circuit_breakers": len(stats),
            "enabled": settings.circuit_breaker_enabled,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}")
        return {
            "error": "Failed to get circuit breaker status",
            "enabled": settings.circuit_breaker_enabled,
            "timestamp": datetime.now(UTC).isoformat(),
        }


@health_router.get("/cache", summary="Cache statistics")
async def cache_status():
    """Get cache statistics and performance metrics."""
    try:
        from ..cache.redis_cache import get_cache_manager

        cache_manager = get_cache_manager()
        stats = await cache_manager.get_stats()

        return {
            "cache_stats": stats.get("cache_stats", {}),
            "redis_info": stats.get("redis_info", {}),
            "hit_rate": stats.get("hit_rate", 0),
            "enabled": settings.cache_enabled,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get cache status: {e}")
        return {
            "error": "Failed to get cache status",
            "enabled": settings.cache_enabled,
            "timestamp": datetime.now(UTC).isoformat(),
        }


@health_router.get("/performance", summary="Performance metrics")
async def performance_metrics():
    """Get performance metrics and system statistics."""
    try:
        from ..performance.background_tasks import get_task_manager
        from ..performance.connection_pool import get_database_pool

        # Get task manager stats
        task_manager = get_task_manager()
        task_stats = await task_manager.get_stats()

        # Get database pool stats
        db_pool = get_database_pool()
        pool_stats = await db_pool.get_pool_status()

        return {
            "background_tasks": task_stats,
            "database_pool": pool_stats,
            "system_info": {
                "max_concurrent_requests": settings.max_concurrent_requests,
                "worker_threads": settings.worker_threads,
                "database_pool_size": settings.database_pool_size,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return {
            "error": "Failed to get performance metrics",
            "timestamp": datetime.now(UTC).isoformat(),
        }
