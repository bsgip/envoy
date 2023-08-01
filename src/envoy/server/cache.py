from asyncio import Lock
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class ExpiringValue(Generic[V]):
    """Represents a generic value that's only valid up to a specified datetime"""

    expiry: Optional[datetime]  # if None - this value never expires
    value: V  # The actual value being stored

    def is_expired(self) -> bool:
        """Returns True if this value is currently expired based on current datetime"""
        if self.expiry:
            return datetime.now(tz=timezone.utc) >= self.expiry
        else:
            return False


class AsyncCache(Generic[K, V]):
    """A simple in memory cache that's 'async safe' but not thread safe. It allows an internal
    cache to be maintained that can be automatically updated on a cache miss.

    This cache is designed to be all or nothing - it does NOT support incremental changes."""

    _cache: dict[K, ExpiringValue[V]]
    _lock: Lock
    _update_fn: Callable[[Any], Awaitable[dict[K, ExpiringValue[V]]]]  # Called when the cache is missed

    def __init__(self, update_fn: Callable[[Any], Awaitable[dict[K, ExpiringValue[V]]]]) -> None:
        """update_fn will be called whenever a cache miss happens during get_value. The return value of this
        function will form the new cache. Exceptions raised will abort the cache update and propagate up
        through the call to get_value"""
        super().__init__()
        self._cache = {}
        self._lock = Lock()
        self._update_fn = update_fn

    async def clear(self):
        """Clears the internal cache - resetting it back to incomplete"""
        async with self._lock:
            self._cache = {}

    def _fetch_from_cache(self, key: K) -> Optional[V]:
        """Internal use only.
        Fetches from cache (respecting expiry times). Returns None if the value DNE or has expired"""
        expiring_value = self._cache.get(key, None)
        if expiring_value and not expiring_value.is_expired():
            return expiring_value.value
        else:
            return None

    async def get_value(self, update_arg: Any, key: K) -> Optional[V]:
        """Attempts to fetch the specified value by key. The internal cache will be utilised first and updated
        if the key is not found / has expired.

        update_arg: Will be passed to the internal update function if a cache update is required
        key: The key to lookup a value

        Returns None if the key DNE or its value has expired (and can't be updated)

        Exceptions raised by the internal update_fn will not be caught and will abort the cache update"""

        # use cache first from outside the lock - the hope is that 99% of requests go this route
        value = self._fetch_from_cache(key)
        if value:
            return value

        # Otherwise acquire the async lock (it won't work with threads - only coroutines)
        # to ensure only one coroutine is doing an update at a time
        async with self._lock:
            # Double check that the cache hasn't updated while we were waiting on the lock
            value = self._fetch_from_cache(key)
            if value:
                return value

            # Perform the cache update
            self._cache = await self._update_fn(update_arg)

            # Now it's the final attempt - either get it or raise an error
            # we do this test from within the lock so we're sure that no other updates
            # can occur - basically - if the ID DNE - it's 100% not in the set of valid public keys
            return self._fetch_from_cache(key)
