"""
MetaMCP Server

Main server application that provides MCP (Model Context Protocol) services
with dynamic tool discovery, semantic search, and enterprise features.
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings, validate_configuration
from .exceptions import MetaMCPException
from .mcp.server import MCPServer
from .monitoring.telemetry import TelemetryManager
from .utils.logging import get_logger, setup_logging
from .utils.rate_limiter import RateLimitMiddleware, create_rate_limiter

logger = get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for recording request metrics."""

    def __init__(self, app, telemetry_manager: TelemetryManager):
        super().__init__(app)
        self.telemetry_manager = telemetry_manager

    async def dispatch(self, request: Request, call_next):
        """Process request and record metrics."""
        import time

        start_time = time.time()

        try:
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            self.telemetry_manager.record_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration=duration,
            )

            return response

        except Exception:
            # Record error metrics
            duration = time.time() - start_time
            self.telemetry_manager.record_request(
                method=request.method,
                path=str(request.url.path),
                status_code=500,
                duration=duration,
            )
            raise


class MetaMCPServer:
    """
    MetaMCP Server Application.

    Main server class that manages the FastAPI application,
    MCP server, and telemetry components.
    """

    def __init__(self):
        """Initialize the MetaMCP server."""
        self.settings = get_settings()
        self.telemetry_manager = TelemetryManager()
        self.mcp_server: MCPServer | None = None
        self.app: FastAPI | None = None
        self._shutdown_event = asyncio.Event()

        # Setup logging
        setup_logging()

        # Validate configuration
        try:
            validate_configuration()
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            sys.exit(1)

    async def initialize(self) -> None:
        """Initialize the server components."""
        try:
            logger.info("Initializing MetaMCP Server...")

            # Initialize telemetry
            if self.settings.telemetry_enabled:
                await self.telemetry_manager.initialize()
                logger.info("Telemetry initialized")

            # Initialize MCP server first
            self.mcp_server = MCPServer()
            await self.mcp_server.initialize()

            # Create FastAPI application after MCP server is initialized
            self.app = self._create_fastapi_app()

            logger.info("MetaMCP Server initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise

    def _create_fastapi_app(self) -> FastAPI:
        """Create and configure FastAPI application."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            # Startup
            logger.info("Starting MetaMCP Server...")
            yield
            # Shutdown
            logger.info("Shutting down MetaMCP Server...")
            await self._shutdown()

        app = FastAPI(
            title=self.settings.app_name,
            version=self.settings.app_version,
            description="MetaMCP - MCP Meta-Server for AI Agents",
            docs_url="/docs" if self.settings.docs_enabled else None,
            redoc_url="/redoc" if self.settings.docs_enabled else None,
            lifespan=lifespan,
        )

        # Add middleware
        self._add_middleware(app)

        # Add exception handlers
        self._add_exception_handlers(app)

        # Add routes
        self._add_routes(app)

        return app

    def _add_middleware(self, app: FastAPI) -> None:
        """Add middleware to the FastAPI application."""

        # CORS middleware (first to handle preflight requests)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.cors_origins,
            allow_credentials=self.settings.cors_allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Gzip middleware
        app.add_middleware(GZipMiddleware, minimum_size=1000)

        # Rate limiting middleware (skip for WebSocket connections)
        rate_limiter = create_rate_limiter(
            use_redis=self.settings.rate_limit_use_redis,
            redis_url=self.settings.rate_limit_redis_url,
        )
        app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

        # Metrics middleware
        if self.settings.telemetry_enabled:
            app.add_middleware(
                MetricsMiddleware, telemetry_manager=self.telemetry_manager
            )

        # Instrument with OpenTelemetry
        if self.settings.telemetry_enabled:
            self.telemetry_manager.instrument_fastapi(app)
            self.telemetry_manager.instrument_httpx()
            self.telemetry_manager.instrument_sqlalchemy()

    def _add_exception_handlers(self, app: FastAPI) -> None:
        """Add exception handlers to the FastAPI application."""

        @app.exception_handler(MetaMCPException)
        async def metamcp_exception_handler(request: Request, exc: MetaMCPException):
            """Handle MetaMCP exceptions."""
            logger.error(
                f"MetaMCP Exception: {exc.message}",
                extra={
                    "error_code": exc.error_code,
                    "status_code": exc.status_code,
                    "path": str(request.url.path),
                },
            )

            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                },
            )

        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """Handle general exceptions."""
            logger.error(
                f"Unhandled Exception: {exc}",
                exc_info=True,
                extra={"path": str(request.url.path)},
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An internal server error occurred",
                    "details": str(exc) if self.settings.debug else None,
                },
            )

    def _add_routes(self, app: FastAPI) -> None:
        """Add routes to the FastAPI application."""

        @app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "name": self.settings.app_name,
                "version": self.settings.app_version,
                "status": "running",
            }

        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}

        @app.get("/metrics")
        async def metrics():
            """Metrics endpoint for Prometheus."""
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

        # Add MCP routes
        if self.mcp_server:
            logger.info(f"Adding MCP routes with router: {self.mcp_server.router}")
            app.include_router(self.mcp_server.router, prefix="/mcp")
            logger.info("MCP routes added successfully")
        else:
            logger.warning("MCP server not available, skipping MCP routes")

    async def _shutdown(self) -> None:
        """Shutdown the server components."""
        try:
            # Shutdown MCP server
            if self.mcp_server:
                await self.mcp_server.shutdown()

            # Shutdown telemetry
            if self.settings.telemetry_enabled:
                await self.telemetry_manager.shutdown()

            logger.info("Server shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run(self) -> None:
        """Run the server."""
        try:
            # Initialize server
            await self.initialize()

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start server
            config = uvicorn.Config(
                app=self.app,
                host=self.settings.host,
                port=self.settings.port,
                reload=self.settings.reload,
                log_level=self.settings.log_level.lower(),
                access_log=True,
            )

            server = uvicorn.Server(config)

            # Run server
            logger.info(f"Starting server on {self.settings.host}:{self.settings.port}")
            await server.serve()

        except Exception as e:
            logger.error(f"Server failed to start: {e}")
            raise
        finally:
            await self._shutdown()


def create_app() -> FastAPI:
    """
    Create FastAPI application for external use.

    Returns:
        FastAPI: Configured FastAPI application
    """
    server = MetaMCPServer()
    return server.app


async def main():
    """Main entry point."""
    server = MetaMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
