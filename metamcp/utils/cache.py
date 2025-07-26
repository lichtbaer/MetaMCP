"""
Caching System

Implementation of a flexible caching system with multiple backends
and caching strategies for improved performance.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class CacheConfig:
    """Configuration for cache."""

    ttl: int = 300  # seconds
    max_size: int = 1000
    enable_compression: bool = False
    enable_serialization: bool = True


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        pass


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend."""

    def __init__(self, config: CacheConfig | None = None):
        """Initialize memory cache backend."""
        self.config = config or CacheConfig()
        self._cache: dict[str, dict[str, Any]] = {}
        self._access_times: dict[str, float] = {}
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key in self._cache:
            entry = self._cache[key]

            # Check expiration
            if entry["expires_at"] and time.time() > entry["expires_at"]:
                await self.delete(key)
                self._misses += 1
                return None

            # Update access time
            self._access_times[key] = time.time()
            self._hits += 1

            return entry["value"]

        self._misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        try:
            # Check cache size limit
            if len(self._cache) >= self.config.max_size:
                await self._evict_oldest()

            # Calculate expiration time
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl
            elif self.config.ttl > 0:
                expires_at = time.time() + self.config.ttl

            # Store entry
            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
            }
            self._access_times[key] = time.time()

            return True

        except Exception as e:
            logger.error(f"Failed to set cache entry: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_times:
                    del self._access_times[key]
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to delete cache entry: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            self._cache.clear()
            self._access_times.clear()
            return True

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if key in self._cache:
            entry = self._cache[key]
            if entry["expires_at"] and time.time() > entry["expires_at"]:
                await self.delete(key)
                return False
            return True
        return False

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        # Clean expired entries
        expired_count = 0
        current_time = time.time()
        for key, entry in list(self._cache.items()):
            if entry["expires_at"] and current_time > entry["expires_at"]:
                await self.delete(key)
                expired_count += 1

        return {
            "backend": "memory",
            "size": len(self._cache),
            "max_size": self.config.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "expired_entries": expired_count,
            "ttl": self.config.ttl,
        }

    async def _evict_oldest(self):
        """Evict oldest cache entries."""
        if not self._access_times:
            return

        # Find oldest accessed entry
        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        await self.delete(oldest_key)


class RedisCacheBackend(CacheBackend):
    """Redis cache backend."""

    def __init__(self, redis_url: str, config: CacheConfig | None = None):
        """Initialize Redis cache backend."""
        self.redis_url = redis_url
        self.config = config or CacheConfig()
        self._redis = None
        self._hits = 0
        self._misses = 0

    async def _get_redis(self):
        """Get Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(self.redis_url)
                await self._redis.ping()
                logger.info("Connected to Redis cache backend")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(key)

            if value is not None:
                self._hits += 1
                return json.loads(value)

            self._misses += 1
            return None

        except Exception as e:
            logger.error(f"Failed to get from Redis cache: {e}")
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        try:
            redis_client = await self._get_redis()
            serialized_value = json.dumps(value)

            if ttl is not None:
                await redis_client.setex(key, ttl, serialized_value)
            elif self.config.ttl > 0:
                await redis_client.setex(key, self.config.ttl, serialized_value)
            else:
                await redis_client.set(key, serialized_value)

            return True

        except Exception as e:
            logger.error(f"Failed to set in Redis cache: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"Failed to delete from Redis cache: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            redis_client = await self._get_redis()
            await redis_client.flushdb()
            return True

        except Exception as e:
            logger.error(f"Failed to clear Redis cache: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            redis_client = await self._get_redis()
            return await redis_client.exists(key) > 0

        except Exception as e:
            logger.error(f"Failed to check existence in Redis cache: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            redis_client = await self._get_redis()
            info = await redis_client.info()

            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "backend": "redis",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "ttl": self.config.ttl,
            }

        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return {"backend": "redis", "error": str(e)}


class Cache:
    """
    Main cache interface.

    Provides a unified interface for caching operations with support
    for multiple backends and caching strategies.
    """

    def __init__(self, backend: CacheBackend, config: CacheConfig | None = None):
        """Initialize cache with backend."""
        self.backend = backend
        self.config = config or CacheConfig()

    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        # Create a string representation of arguments
        key_parts = []

        # Add positional arguments
        for arg in args:
            key_parts.append(str(arg))

        # Add keyword arguments (sorted for consistency)
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")

        # Create hash of the key string using hashlib for deterministic results
        key_string = "|".join(key_parts)
        import hashlib

        hash_bytes = hashlib.sha256(key_string.encode()).digest()
        # Convert to hex and truncate to 32 characters for cache key
        return hash_bytes.hex()[:32]

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        return await self.backend.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        return await self.backend.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return await self.backend.delete(key)

    async def clear(self) -> bool:
        """Clear all cache entries."""
        return await self.backend.clear()

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return await self.backend.exists(key)

    async def get_or_set(self, key: str, default_func, ttl: int | None = None) -> Any:
        """
        Get value from cache or set default if not exists.

        Args:
            key: Cache key
            default_func: Function to call if key doesn't exist
            ttl: Time to live in seconds

        Returns:
            Cached value or default
        """
        value = await self.get(key)
        if value is None:
            if asyncio.iscoroutinefunction(default_func):
                value = await default_func()
            else:
                value = default_func()

            await self.set(key, value, ttl)

        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.

        Args:
            pattern: Pattern to match keys

        Returns:
            Number of invalidated entries
        """
        # This is a simplified implementation
        # In production, you might want to use Redis SCAN or similar
        count = 0
        # Implementation would depend on backend capabilities
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return asyncio.create_task(self.backend.get_stats())


def cache(ttl: int | None = None, key_prefix: str = ""):
    """
    Decorator for caching function results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys

    Returns:
        Decorated function
    """

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key_data = str(args) + str(sorted(kwargs.items()))
            cache_key = f"{key_prefix}:{func.__name__}:{hash(key_data)}"

            # Get cache instance (this would be injected or global)
            cache_instance = get_cache_instance()

            # Try to get from cache
            cached_result = await cache_instance.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Cache result
            await cache_instance.set(cache_key, result, ttl)

            return result

        def sync_wrapper(*args, **kwargs):
            # For sync functions, we'd need to handle differently
            # This is a simplified version - sync caching would require
            # a different approach with thread-safe operations
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Global cache instance
_cache_instance: Cache | None = None


def get_cache_instance() -> Cache:
    """Get global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        # Default to memory cache
        backend = MemoryCacheBackend()
        _cache_instance = Cache(backend)
    return _cache_instance


def set_cache_instance(cache_instance: Cache):
    """Set global cache instance."""
    global _cache_instance
    _cache_instance = cache_instance


def create_memory_cache(config: CacheConfig | None = None) -> Cache:
    """Create memory cache instance."""
    backend = MemoryCacheBackend(config)
    return Cache(backend, config)


def create_redis_cache(redis_url: str, config: CacheConfig | None = None) -> Cache:
    """Create Redis cache instance."""
    backend = RedisCacheBackend(redis_url, config)
    return Cache(backend, config)
