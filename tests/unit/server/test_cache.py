import unittest.mock as mock
from asyncio import sleep
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from assertical.fake.asyncio import create_async_result

from envoy.server.cache import AsyncCache, ExpiringValue


@dataclass
class MyCustomArgument:
    string_val: str
    int_val: int


class MyCustomError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def make_delta_now(delta: Optional[timedelta]) -> Optional[datetime]:
    if delta is None:
        return None
    else:
        return datetime.now(tz=timezone.utc) + delta


@pytest.mark.parametrize(
    "delta_now, expired",
    [
        (timedelta(seconds=20), False),
        (timedelta(days=20), False),
        (timedelta(seconds=0), True),
        (timedelta(seconds=-20), True),
        (timedelta(days=-20), True),
        (None, False),
    ],
)
def test_expiring_value(delta_now: Optional[timedelta], expired: bool):
    """Tests is_expired behaves for a variety of values based on datetime.now"""
    expiry = make_delta_now(delta_now)
    assert ExpiringValue(expiry, "string val").is_expired() == expired
    assert ExpiringValue(expiry, 123).is_expired() == expired


@pytest.mark.anyio
async def test_initial_clear():
    """Tests that clearing an empty cache does nothing"""
    mock_update_fn = mock.Mock()
    c = AsyncCache(mock_update_fn)
    assert c._cache == {}
    await c.clear()
    mock_update_fn.assert_not_called()
    assert c._cache == {}


@pytest.mark.anyio
async def test_update_result_cached():
    updated_cache = {
        "key1": ExpiringValue(make_delta_now(timedelta(hours=5)), "val1"),
        "key2": ExpiringValue(make_delta_now(None), "val2"),
        "key3": ExpiringValue(make_delta_now(timedelta(hours=-1)), "val3"),  # Expired
    }
    update_arg = MyCustomArgument("abc123", 456)
    mock_update_fn = mock.Mock(return_value=create_async_result(updated_cache))
    c = AsyncCache(mock_update_fn)

    # Fetching key1/key2 works fine and only updates the cache once
    assert (await c.get_value(update_arg, "key1")) == "val1"
    assert (await c.get_value(update_arg, "key2")) == "val2"
    mock_update_fn.assert_called_once_with(update_arg)

    # Fetching key3 causes the cache to update again (as it's expired - because it's expired it returns None)
    assert (await c.get_value(update_arg, "key3")) is None
    assert mock_update_fn.call_count == 2
    mock_update_fn.assert_called_with(update_arg)

    # We can still fetch key1/key2 as they were also returned in the cache update
    assert (await c.get_value(update_arg, "key1")) == "val1"
    assert (await c.get_value(update_arg, "key2")) == "val2"
    assert mock_update_fn.call_count == 2, "Call count shouldn't have changed from before"

    # Fetching key4 causes the cache to update again (as it DNE)
    assert (await c.get_value(update_arg, "key4")) is None
    assert mock_update_fn.call_count == 3
    mock_update_fn.assert_called_with(update_arg)

    # We can still fetch key1/key2 as they were also returned in the cache update
    assert (await c.get_value(update_arg, "key1")) == "val1"
    assert (await c.get_value(update_arg, "key2")) == "val2"
    assert mock_update_fn.call_count == 3, "Call count shouldn't have changed from before"


@pytest.mark.anyio
async def test_update_raise_error():
    """Tests that updates that raise an error dont invalidate the old cache"""
    updated_cache = {
        "key1": ExpiringValue(make_delta_now(timedelta(hours=5)), "val1"),
        "key2": ExpiringValue(make_delta_now(None), "val2"),
    }
    update_arg = MyCustomArgument("abc123", 456)
    mock_update_fn = mock.Mock(return_value=create_async_result(updated_cache))
    c = AsyncCache(mock_update_fn)

    # Fetching key1/key2 works fine and only updates the cache once
    assert (await c.get_value(update_arg, "key1")) == "val1"
    assert (await c.get_value(update_arg, "key1")) == "val1"
    assert (await c.get_value(update_arg, "key2")) == "val2"
    assert (await c.get_value(update_arg, "key2")) == "val2"
    mock_update_fn.assert_called_once_with(update_arg)

    # Now trigger an update that raises an error
    mock_update_fn.side_effect = MyCustomError()
    with pytest.raises(MyCustomError):
        await c.get_value(update_arg, "key3")
    assert mock_update_fn.call_count == 2
    mock_update_fn.assert_called_with(update_arg)

    # We can still fetch key1/key2 as the cache should be left alone
    assert (await c.get_value(update_arg, "key1")) == "val1"
    assert (await c.get_value(update_arg, "key2")) == "val2"
    assert mock_update_fn.call_count == 2, "Call count shouldn't have changed from before"


@pytest.mark.anyio
async def test_force_update():
    """Tests that force_update persists in the face of errors being raised and waits the suitable amount of time"""
    updated_cache = {
        "key1": ExpiringValue(make_delta_now(timedelta(hours=5)), "val1"),
        "key2": ExpiringValue(make_delta_now(None), "val2"),
    }
    update_arg = MyCustomArgument("def123", 457)
    delay_secs = 1.0
    mock_update_fn = mock.Mock(
        side_effect=[
            MyCustomError("My custom error"),
            MyCustomError("My other error"),
            Exception("My normal ex"),
            create_async_result(updated_cache),
        ]
    )
    c = AsyncCache(mock_update_fn, force_update_delay_seconds=delay_secs)

    # Act
    start = datetime.now()
    await c.force_update(update_arg)
    end = datetime.now()

    # Assert
    total_seconds = (end - start).seconds
    assert (
        total_seconds >= 3 and total_seconds <= 4
    ), f"{total_seconds} should roughly match the number of errors (3) * delay_secs ({delay_secs})"
    assert mock_update_fn.call_count == 4, "3 errors and 1 valid update"
    assert all([len(a.args) == 1 for a in mock_update_fn.call_args_list]), "Only a single arg passed to update_fn"
    assert [a.args[0] for a in mock_update_fn.call_args_list] == [
        update_arg,
        update_arg,
        update_arg,
        update_arg,
    ], "Should always pass update_arg to update_fn"

    # Cache should now be populated
    assert (await c.get_value(update_arg, "key1")) == "val1", "Cache should be populated"
    assert (await c.get_value(update_arg, "key2")) == "val2", "Cache should be populated"
    assert mock_update_fn.call_count == 4, "This must be unchanged after the get_value calls (i.e - the cache is used)"


@pytest.mark.anyio
async def test_get_value_sync():
    """Validates that running the sync method triggers a background task to execute"""
    updated_cache = {
        "key1": ExpiringValue(make_delta_now(timedelta(hours=5)), "val1"),
        "key2": ExpiringValue(make_delta_now(None), "val2"),
    }
    update_arg = MyCustomArgument("def123", 457)
    mock_update_fn = mock.Mock(return_value=create_async_result(updated_cache))
    c = AsyncCache(mock_update_fn)

    # Trigger the update in the background
    assert c.get_value_sync(update_arg, "key1") is None, "This will return none due to cache miss"
    await sleep(1)  # We need an async wait so that the background task has a chance to run

    # It should now be populated
    assert c.get_value_sync(update_arg, "key1") == "val1", "This should've been updated in the background"
    assert c.get_value_sync(update_arg, "key2") == "val2", "This should've been updated in the background"
    assert mock_update_fn.call_count == 1
