"""Thread-safe LRU cache with TTL expiration for external APIs.

Features:
- Configurable max size (LRU eviction when full)
- Per-entry TTL expiration (monotonic clock)
- Async-safe via asyncio.Lock
- String keys for multi-purpose caching (e.g. "metadata:42", "avro:42")
- Hit/miss statistics for monitoring
"""

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cached item with creation timestamp and hit counter."""

    data: dict
    created_at: float  # time.monotonic()
    hit_count: int = 0


class MetadataCache:
    """Async-safe LRU cache with TTL.

    Keys are strings to support multiple data types:
    - "metadata:{dataset_id}" for dataset metadata
    - "avro:{dataset_id}" for Avro schema
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    @property
    def max_size(self) -> int:
        return self._max_size

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    async def get(self, key: str) -> dict | None:
        """Get cached data. Returns None on miss or expiration."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            elapsed = time.monotonic() - entry.created_at
            if elapsed > self._ttl_seconds:
                del self._cache[key]
                self._misses += 1
                logger.debug("Cache expired: key=%s (%.1fs)", key, elapsed)
                return None

            self._cache.move_to_end(key)
            entry.hit_count += 1
            self._hits += 1
            return entry.data

    async def put(self, key: str, data: dict) -> None:
        """Store data in cache. Evicts LRU entry if at capacity."""
        async with self._lock:
            if key in self._cache:
                self._cache[key] = CacheEntry(data=data, created_at=time.monotonic())
                self._cache.move_to_end(key)
                return

            while len(self._cache) >= self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("Cache LRU eviction: key=%s", evicted_key)

            self._cache[key] = CacheEntry(data=data, created_at=time.monotonic())

    async def invalidate(self, key: str) -> bool:
        """Remove a specific entry. Returns True if found and removed."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug("Cache invalidated: key=%s", key)
                return True
            return False

    async def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries whose key starts with prefix. Returns count."""
        async with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]
            if keys_to_remove:
                logger.debug("Cache invalidated %d keys prefix=%s", len(keys_to_remove), prefix)
            return len(keys_to_remove)

    async def clear(self) -> int:
        """Clear all entries. Returns count of removed entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info("Cache cleared: %d entries removed", count)
            return count

    async def stats(self) -> dict:
        """Return cache statistics."""
        async with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
                "total_requests": total,
            }

    async def reconfigure(
        self,
        max_size: int | None = None,
        ttl_seconds: int | None = None,
    ) -> dict:
        """Update cache configuration. Evicts entries if new max_size is smaller."""
        async with self._lock:
            if max_size is not None:
                self._max_size = max_size
                while len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)

            if ttl_seconds is not None:
                self._ttl_seconds = ttl_seconds

            return {
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
                "current_size": len(self._cache),
            }


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

_cache: MetadataCache | None = None


def get_cache() -> MetadataCache:
    """Return the global cache instance."""
    global _cache
    if _cache is None:
        from app.core.config import settings

        _cache = MetadataCache(
            max_size=settings.cache_max_size,
            ttl_seconds=settings.cache_ttl_seconds,
        )
        logger.info(
            "MetadataCache initialized: max_size=%d, ttl=%ds",
            settings.cache_max_size,
            settings.cache_ttl_seconds,
        )
    return _cache


def reset_cache() -> None:
    """Reset the singleton (for reconfiguration)."""
    global _cache
    _cache = None
