"""
Redis Cache Implementation

This module provides a Redis-based caching system with various cache strategies,
TTL management, and performance optimizations.
"""

import asyncio
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RedisCache:
    """Redis-based caching implementation."""

    def __init__(self, redis_url: str = None):
        """Initialize Redis cache."""
        self.redis_url = redis_url or settings.redis_url
        self._redis = None
        self._lock = asyncio.Lock()
        self._connection_pool = None
        self.default_ttl = 3600  # 1 hour
        self.max_ttl = 86400 * 7  # 1 week

    async def _get_redis(self):
        """Get Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=False,  # Keep as bytes for pickle
                    max_connections=20,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                )
                await self._redis.ping()
                logger.info(f"Connected to Redis cache: {self.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis cache: {e}")
                raise
        return self._redis

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(key)

            if value is None:
                return default

            # Try to deserialize
            try:
                return pickle.loads(value)
            except (pickle.PickleError, TypeError):
                # Fallback to JSON
                try:
                    return json.loads(value.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return value.decode("utf-8")

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default

    async def set(
        self, key: str, value: Any, ttl: int = None, serialize: bool = True
    ) -> bool:
        """Set value in cache."""
        try:
            redis_client = await self._get_redis()

            # Determine TTL
            if ttl is None:
                ttl = self.default_ttl
            elif ttl > self.max_ttl:
                ttl = self.max_ttl

            # Serialize value
            if serialize:
                if isinstance(value, (dict, list, int, float, bool)):
                    serialized = pickle.dumps(value)
                else:
                    serialized = str(value).encode("utf-8")
            else:
                serialized = value

            # Set with TTL
            result = await redis_client.setex(key, ttl, serialized)
            return bool(result)

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get TTL for key."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.ttl(key)
            return result
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return -1

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.expire(key, ttl)
            return bool(result)
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        try:
            redis_client = await self._get_redis()
            keys = await redis_client.keys(pattern)
            if keys:
                result = await redis_client.delete(*keys)
                logger.info(f"Cleared {result} keys matching pattern: {pattern}")
                return result
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        try:
            redis_client = await self._get_redis()
            values = await redis_client.mget(keys)

            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = pickle.loads(value)
                    except (pickle.PickleError, TypeError):
                        try:
                            result[key] = json.loads(value.decode("utf-8"))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            result[key] = value.decode("utf-8")

            return result

        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}

    async def set_many(self, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set multiple values in cache."""
        try:
            redis_client = await self._get_redis()

            # Prepare pipeline
            pipe = redis_client.pipeline()

            for key, value in data.items():
                if isinstance(value, (dict, list, int, float, bool)):
                    serialized = pickle.dumps(value)
                else:
                    serialized = str(value).encode("utf-8")

                if ttl is None:
                    ttl = self.default_ttl

                pipe.setex(key, ttl, serialized)

            # Execute pipeline
            await pipe.execute()
            return True

        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter in cache."""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.incrby(key, amount)
            return result
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0

    async def close(self):
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None


class CacheManager:
    """Cache manager with different cache strategies."""

    def __init__(self, redis_url: str = None):
        """Initialize cache manager."""
        self.redis_cache = RedisCache(redis_url)
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }

    async def get(
        self, key: str, default: Any = None, strategy: str = "default"
    ) -> Any:
        """Get value with cache strategy."""
        try:
            # Check cache
            value = await self.redis_cache.get(key)

            if value is not None:
                self._cache_stats["hits"] += 1
                logger.debug(f"Cache HIT for key: {key}")
                return value
            else:
                self._cache_stats["misses"] += 1
                logger.debug(f"Cache MISS for key: {key}")
                return default

        except Exception as e:
            logger.error(f"Cache manager get error: {e}")
            return default

    async def set(
        self, key: str, value: Any, ttl: int = None, strategy: str = "default"
    ) -> bool:
        """Set value with cache strategy."""
        try:
            # Apply strategy-specific TTL
            if strategy == "short":
                ttl = ttl or 300  # 5 minutes
            elif strategy == "long":
                ttl = ttl or 86400  # 1 day
            elif strategy == "session":
                ttl = ttl or 3600  # 1 hour
            else:
                ttl = ttl or 3600  # 1 hour default

            result = await self.redis_cache.set(key, value, ttl)
            if result:
                self._cache_stats["sets"] += 1
                logger.debug(f"Cache SET for key: {key} (TTL: {ttl}s)")

            return result

        except Exception as e:
            logger.error(f"Cache manager set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            result = await self.redis_cache.delete(key)
            if result:
                self._cache_stats["deletes"] += 1
            return result
        except Exception as e:
            logger.error(f"Cache manager delete error: {e}")
            return False

    async def clear_tool_cache(self, tool_name: str = None) -> int:
        """Clear tool-related cache."""
        if tool_name:
            pattern = f"tool:{tool_name}:*"
        else:
            pattern = "tool:*"
        return await self.redis_cache.clear_pattern(pattern)

    async def clear_user_cache(self, user_id: str = None) -> int:
        """Clear user-related cache."""
        if user_id:
            pattern = f"user:{user_id}:*"
        else:
            pattern = "user:*"
        return await self.redis_cache.clear_pattern(pattern)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis_client = await self.redis_cache._get_redis()
            info = await redis_client.info()

            return {
                "cache_stats": self._cache_stats.copy(),
                "redis_info": {
                    "used_memory": info.get("used_memory", 0),
                    "used_memory_peak": info.get("used_memory_peak", 0),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                },
                "hit_rate": (
                    self._cache_stats["hits"]
                    / (self._cache_stats["hits"] + self._cache_stats["misses"])
                    if (self._cache_stats["hits"] + self._cache_stats["misses"]) > 0
                    else 0
                ),
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {"cache_stats": self._cache_stats.copy()}

    async def close(self):
        """Close cache manager."""
        await self.redis_cache.close()


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_url: str = None) -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url)
    return _cache_manager


async def close_cache_manager():
    """Close global cache manager."""
    global _cache_manager
    if _cache_manager is not None:
        await _cache_manager.close()
        _cache_manager = None
