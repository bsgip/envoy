import logging
from asyncio import Lock, get_running_loop, run, sleep
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from envoy.server.manager.time import utc_now

logger = logging.getLogger(__name__)

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
            return utc_now() >= self.expiry
        else:
            return False


class AsyncCache(Generic[K, V]):
    """A simple in memory cache that's 'async safe' but not thread safe. It allows an internal
    cache to be maintained that can be automatically updated on a cache miss.

    This cache is designed to be all or nothing - it does NOT support incremental changes."""

    _cache: dict[K, ExpiringValue[V]]
    _lock: Lock
    _update_fn: Callable[[Any], Awaitable[dict[K, ExpiringValue[V]]]]  # Called when the cache is missed
    _force_update_delay_seconds: float  # How long force_update should wait between attempts (in seconds)

    def __init__(
        self, update_fn: Callable[[Any], Awaitable[dict[K, ExpiringValue[V]]]], force_update_delay_seconds: float = 1.0
    ) -> None:
        """update_fn will be called whenever a cache miss happens during get_value. The return value of this
        function will form the new cache. Exceptions raised will abort the cache update and propagate up
        through the call to get_value"""
        super().__init__()
        self._cache = {}
        self._lock = Lock()
        self._update_fn = update_fn
        self._force_update_delay_seconds = force_update_delay_seconds

    async def clear(self) -> None:
        """Clears the internal cache - resetting it back to incomplete"""
        async with self._lock:
            self._cache = {}

    def _fetch_from_cache(self, key: K) -> tuple[Optional[V], Optional[ExpiringValue[V]]]:
        """Internal use only.
        Fetches from cache (respecting expiry times). Returns None if the value DNE or has expired"""
        expiring_value = self._cache.get(key, None)
        if expiring_value and not expiring_value.is_expired():
            return (expiring_value.value, expiring_value)
        else:
            return (None, expiring_value)

    async def get_value_ignore_expiry(self, update_arg: Any, key: K) -> Optional[ExpiringValue[V]]:
        """Attempts to fetch the specified value by key. The internal cache will be utilised
        first and updated if the key is not found / has expired.

        This function differs from get_value in that it will return the full ExpiringValue even if it's marked
        as expired (but will attempt to update the cache BEFORE returning the expired value).

        update_arg: Will be passed to the internal update function if a cache update is required
        key: The key to lookup a value

        Returns None if the key DNE, otherwise the value (expired or not) will be returned

        Exceptions raised by the internal update_fn will not be caught and will abort the cache update"""

        # use cache first from outside the lock - the hope is that 99% of requests go this route
        (value, expiring_value) = self._fetch_from_cache(key)
        if value:
            return expiring_value

        # Otherwise acquire the async lock (it won't work with threads - only coroutines)
        # to ensure only one coroutine is doing an update at a time
        async with self._lock:
            # Double check that the cache hasn't updated while we were waiting on the lock
            (value, expiring_value) = self._fetch_from_cache(key)
            if value:
                return expiring_value

            # Perform the cache update
            self._cache = await self._update_fn(update_arg)

            # Now it's the final attempt - either get it or raise an error
            # we do this test from within the lock so we're sure that no other updates
            # can occur - basically - if the ID DNE - it's 100% not in the set of valid public keys
            (value, expiring_value) = self._fetch_from_cache(key)
            return expiring_value

    async def get_value(self, update_arg: Any, key: K) -> Optional[V]:
        """Attempts to fetch the specified value by key. The internal cache will be utilised first and updated
        if the key is not found / has expired.

        update_arg: Will be passed to the internal update function if a cache update is required
        key: The key to lookup a value

        Returns None if the key DNE or its value has expired (and can't be updated)

        Exceptions raised by the internal update_fn will not be caught and will abort the cache update"""

        # use cache first from outside the lock - the hope is that 99% of requests go this route
        expiring_value = await self.get_value_ignore_expiry(update_arg, key)
        if expiring_value is None or expiring_value.is_expired():
            return None

        return expiring_value.value

    async def force_update(self, update_arg: Any) -> None:
        """Forces an update to occur - will hold the internal cache lock and repeatedly attempt
        to update the cache until successful. Exceptions will be caught and logged but will not be raised.

        This is a highly aggressive update method - it's designed to run until successful"""
        async with self._lock:
            while True:
                try:
                    self._cache = await self._update_fn(update_arg)
                    return  # Try until successful
                except Exception as ex:
                    logger.error(f"force_update error. Retry : {ex}")
                    await sleep(self._force_update_delay_seconds)

    def get_value_sync(self, update_arg: Any, key: K) -> Optional[V]:
        """Similar to get_value but without the async. This will ONLY utilise the internal cache, in the event
        of a cache miss/expired value None will be returned but force_update will be triggered in a background
        async task on the current asyncio event loop

        update_arg: Will be passed to the internal update function if a cache update is required
        key: The key to lookup a value

        Exceptions raised by force_update will not propagate upwards"""

        (value, _) = self._fetch_from_cache(key)
        if value:
            return value

        # At this point we need a cache update - we can't wait for the update so we fire and forget a call
        # to force_update which "should" guarantee an eventual update

        # Adapted from
        # https://stackoverflow.com/questions/55409641/asyncio-run-cannot-be-called-from-a-running-event-loop-when-using-jupyter-no  # noqa e501
        try:
            loop = get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no current event loop...'
            loop = None

        if loop and loop.is_running():
            logger.info("Async event loop already running. Adding force_update coroutine to the event loop.")
            loop.create_task(self.force_update(update_arg))
        else:
            logger.info("Starting new event loop to execute force_update")
            run(self.force_update(update_arg))

        return None
