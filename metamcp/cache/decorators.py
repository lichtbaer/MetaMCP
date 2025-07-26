"""
Cache Decorators

This module provides decorators for easy caching integration.
"""

import functools
import hashlib
import json
from typing import Any, Callable, Dict, Optional

from ..utils.logging import get_logger
from .redis_cache import get_cache_manager

logger = get_logger(__name__)


def cache_result(
    ttl: int = 3600,
    key_prefix: str = "",
    strategy: str = "default",
    key_generator: Callable = None,
):
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        strategy: Cache strategy (default, short, long, session)
        key_generator: Custom key generation function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_generator:
                cache_key = key_generator(func, args, kwargs)
            else:
                cache_key = _generate_cache_key(func, args, kwargs, key_prefix)

            # Get cache manager
            cache_manager = get_cache_manager()

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, strategy=strategy)
            if cached_result is not None:
                logger.debug(f"Cache HIT for {func.__name__}: {cache_key}")
                return cached_result

            # Execute function
            logger.debug(f"Cache MISS for {func.__name__}: {cache_key}")
            result = await func(*args, **kwargs)

            # Cache result
            await cache_manager.set(cache_key, result, ttl, strategy)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we'll need to handle this differently
            # For now, just execute without caching
            logger.warning(
                f"Sync function {func.__name__} cannot be cached with async decorator"
            )
            return func(*args, **kwargs)

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_invalidate(pattern: str = None, key_generator: Callable = None):
    """
    Decorator to invalidate cache after function execution.

    Args:
        pattern: Cache key pattern to invalidate
        key_generator: Custom key generation function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute function first
            result = await func(*args, **kwargs)

            # Invalidate cache
            cache_manager = get_cache_manager()

            if pattern:
                # Invalidate by pattern
                cleared = await cache_manager.redis_cache.clear_pattern(pattern)
                logger.debug(
                    f"Invalidated {cleared} cache entries with pattern: {pattern}"
                )
            elif key_generator:
                # Invalidate specific key
                cache_key = key_generator(func, args, kwargs)
                await cache_manager.delete(cache_key)
                logger.debug(f"Invalidated cache key: {cache_key}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Execute function
            result = func(*args, **kwargs)

            # For sync functions, we'll need async context
            # This is a limitation - sync functions can't easily invalidate async cache
            logger.warning(
                f"Sync function {func.__name__} cache invalidation not supported"
            )
            return result

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_method_result(
    ttl: int = 3600,
    key_prefix: str = "",
    strategy: str = "default",
    include_self: bool = False,
):
    """
    Decorator to cache method results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        strategy: Cache strategy
        include_self: Include self object in cache key
    """

    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        async def async_wrapper(self, *args, **kwargs):
            # Generate cache key
            if include_self:
                # Include relevant parts of self object
                self_key = _get_object_key(self)
                cache_key = _generate_cache_key(
                    method, (self_key,) + args, kwargs, key_prefix
                )
            else:
                cache_key = _generate_cache_key(method, args, kwargs, key_prefix)

            # Get cache manager
            cache_manager = get_cache_manager()

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key, strategy=strategy)
            if cached_result is not None:
                logger.debug(f"Cache HIT for {method.__name__}: {cache_key}")
                return cached_result

            # Execute method
            logger.debug(f"Cache MISS for {method.__name__}: {cache_key}")
            result = await method(self, *args, **kwargs)

            # Cache result
            await cache_manager.set(cache_key, result, ttl, strategy)

            return result

        @functools.wraps(method)
        def sync_wrapper(self, *args, **kwargs):
            # For sync methods, we'll need to handle this differently
            logger.warning(
                f"Sync method {method.__name__} cannot be cached with async decorator"
            )
            return method(self, *args, **kwargs)

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(method):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _generate_cache_key(
    func: Callable, args: tuple, kwargs: dict, prefix: str = ""
) -> str:
    """Generate cache key from function and arguments."""
    # Create a unique identifier
    func_name = func.__name__
    module_name = func.__module__

    # Serialize arguments
    args_str = json.dumps(args, sort_keys=True, default=str)
    kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)

    # Create key components
    key_parts = [prefix, module_name, func_name, args_str, kwargs_str]
    key_string = ":".join(filter(None, key_parts))

    # Hash the key to keep it reasonable length
    key_hash = hashlib.md5(key_string.encode()).hexdigest()

    return f"cache:{key_hash}"


def _get_object_key(obj: Any) -> str:
    """Get a unique key for an object."""
    try:
        # Try to get object ID or hash
        if hasattr(obj, "__hash__") and obj.__hash__ is not None:
            return str(hash(obj))
        elif hasattr(obj, "id"):
            return str(obj.id)
        elif hasattr(obj, "__dict__"):
            # Use relevant attributes
            relevant_attrs = ["id", "name", "key", "uuid"]
            for attr in relevant_attrs:
                if hasattr(obj, attr):
                    return f"{obj.__class__.__name__}:{getattr(obj, attr)}"
            # Fallback to class name and object id
            return f"{obj.__class__.__name__}:{id(obj)}"
        else:
            return str(id(obj))
    except Exception:
        return str(id(obj))


# Import asyncio for coroutine detection
import asyncio
