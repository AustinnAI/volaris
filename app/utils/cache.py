"""
Redis Cache Utility
Wrapper for Upstash Redis REST API with async support.
"""

import json
from typing import Any, Optional
import httpx
from app.config import settings


class RedisCache:
    """
    Redis cache client using Upstash REST API.
    Provides simple get/set/delete operations with TTL support.
    """

    def __init__(self):
        self.base_url = settings.UPSTASH_REDIS_REST_URL.rstrip("/")
        self.token = settings.UPSTASH_REDIS_REST_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        try:
            response = await self.client.get(f"{self.base_url}/get/{key}")
            response.raise_for_status()
            data = response.json()
            result = data.get("result")

            if result is None:
                return None

            # Try to deserialize JSON, return raw string if fails
            try:
                return json.loads(result)
            except (json.JSONDecodeError, TypeError):
                return result

        except httpx.HTTPStatusError:
            return None
        except Exception as e:
            print(f"Redis GET error for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: settings.REDIS_TTL_DEFAULT)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize value to JSON
            serialized_value = json.dumps(value)
            ttl = ttl or settings.REDIS_TTL_DEFAULT

            # Use SETEX command for atomic set with TTL
            payload = ["SETEX", key, ttl, serialized_value]
            response = await self.client.post(
                self.base_url,
                json=payload,
            )
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Redis SET error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self.client.post(
                self.base_url,
                json=["DEL", key],
            )
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Redis DELETE error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        try:
            response = await self.client.post(
                self.base_url,
                json=["EXISTS", key],
            )
            response.raise_for_status()
            data = response.json()
            return data.get("result", 0) == 1

        except Exception as e:
            print(f"Redis EXISTS error for key {key}: {e}")
            return False

    async def flush_all(self) -> bool:
        """
        Clear all keys from cache.
        Use with caution!

        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self.client.post(
                self.base_url,
                json=["FLUSHDB"],
            )
            response.raise_for_status()
            return True

        except Exception as e:
            print(f"Redis FLUSHDB error: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client connection"""
        await self.client.aclose()


# Global cache instance
cache = RedisCache()
