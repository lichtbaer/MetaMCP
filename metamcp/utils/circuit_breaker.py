"""
Circuit Breaker Implementation

This module provides a circuit breaker pattern implementation for external service calls,
with configurable failure thresholds, recovery strategies, and monitoring capabilities.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout: int = 60  # Seconds to wait before trying half-open
    expected_exception: type = Exception  # Exception type to count as failure
    success_threshold: int = 2  # Number of successes to close circuit again


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    current_state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.

    Provides fault tolerance by monitoring failures and temporarily
    stopping calls to failing services.
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[str, CircuitState], None]] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name for identification
            config: Configuration parameters
            on_state_change: Callback for state changes
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change

        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_success_time = None
        self._lock = asyncio.Lock()

        # Statistics
        self.stats = CircuitBreakerStats()

        logger.info(f"Circuit breaker '{name}' initialized with config: {self.config}")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self._state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self._state == CircuitState.HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original function exception
        """
        async with self._lock:
            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._set_state(CircuitState.HALF_OPEN)
                    logger.info(f"Circuit breaker '{self.name}' moved to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {self._last_failure_time}"
                    )

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success - update state
            await self._on_success()
            return result

        except self.config.expected_exception:
            # Failure - update state
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._failure_count = 0
            self._success_count += 1
            self._last_success_time = time.time()

            # Update statistics
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.last_success_time = self._last_success_time

            # Close circuit if in half-open state
            if self._state == CircuitState.HALF_OPEN:
                if self._success_count >= self.config.success_threshold:
                    await self._set_state(CircuitState.CLOSED)
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' moved to CLOSED")

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            # Update statistics
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.last_failure_time = self._last_failure_time

            # Open circuit if threshold reached
            if self._failure_count >= self.config.failure_threshold:
                if self._state != CircuitState.OPEN:
                    await self._set_state(CircuitState.OPEN)
                    logger.warning(
                        f"Circuit breaker '{self.name}' opened after "
                        f"{self._failure_count} failures"
                    )

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if not self._last_failure_time:
            return False

        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout

    async def _set_state(self, new_state: CircuitState) -> None:
        """Set circuit state and trigger callback."""
        if self._state != new_state:
            self._state = new_state
            self.stats.current_state = new_state

            # Trigger callback if provided
            if self.on_state_change:
                try:
                    self.on_state_change(self.name, new_state)
                except Exception as e:
                    logger.error(f"Error in circuit breaker state change callback: {e}")

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self.stats.current_state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers.

    Provides centralized management and monitoring of circuit breakers.
    """

    def __init__(self):
        """Initialize circuit breaker manager."""
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker.

        Args:
            name: Circuit breaker name
            config: Configuration (only used for new instances)

        Returns:
            Circuit breaker instance
        """
        async with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(
                    name=name,
                    config=config,
                    on_state_change=self._on_state_change,
                )

            return self._circuit_breakers[name]

    def _on_state_change(self, name: str, state: CircuitState) -> None:
        """Handle circuit breaker state changes."""
        logger.info(f"Circuit breaker '{name}' state changed to {state.value}")

    async def get_all_stats(self) -> dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers."""
        return {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}

    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self._circuit_breakers.values():
            cb.reset()

    async def close(self) -> None:
        """Close circuit breaker manager."""
        # Reset all circuit breakers
        await self.reset_all()
        self._circuit_breakers.clear()


# Global circuit breaker manager instance
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager instance."""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager


async def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """
    Get circuit breaker by name.

    Args:
        name: Circuit breaker name
        config: Configuration (only used for new instances)

    Returns:
        Circuit breaker instance
    """
    manager = get_circuit_breaker_manager()
    return await manager.get_circuit_breaker(name, config)
