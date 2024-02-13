import unittest.mock as mock
from typing import Any

from taskiq import AsyncBroker


def create_mock_broker() -> mock.Mock:
    """creates a new fully mocked AsyncSession"""
    return mock.AsyncMock(spec_set=AsyncBroker)


def configure_mock_task(m: mock.MagicMock):
    """Given a mock - configure it as if it were a TaskIQ task"""
    kicker_instance = mock.Mock()
    m.kicker.return_value = kicker_instance

    kicker_instance.with_broker = mock.Mock(return_value=kicker_instance)
    kicker_instance.kiq = mock.AsyncMock(return_value=1)


def get_mock_task_kicker_call_args(m: mock.MagicMock) -> mock._CallList:
    """Gets all the call arguments to kiq for a mock_task"""
    return m.kicker.return_value.kiq.call_args_list


def assert_task_kicked_n_times(m: mock.MagicMock, n: int):
    """Asserts that a particular task was kicked EXACTLY n times"""
    assert m.kicker.call_count == n
    assert m.kicker.return_value.with_broker.call_count == n
    assert m.kicker.return_value.kiq.call_count == n


def assert_task_kicked_with_broker_and_args(m: mock.MagicMock, broker: AsyncBroker, **kwargs: Any):
    """Asserts that a particular task mock was kicked with a particular broker (and optionally validating the
    passed params were included)"""

    # First we need to find the call that
    index = -1
    all_call_args = get_mock_task_kicker_call_args(m)
    for call_index, call_args in enumerate(all_call_args):
        matched_kwargs = True
        for arg, arg_val in kwargs.items():
            if arg not in call_args.kwargs or arg_val != call_args.kwargs[arg]:
                matched_kwargs = False
                break

        if matched_kwargs:
            index = call_index
            break

    assert (
        index >= 0
    ), f"Couldn't find a call to kiq with kwargs {kwargs}. Options include {[a.kwargs for a in all_call_args]}"

    assert (
        m.kicker.return_value.with_broker.call_args_list[index].args[0] is broker
    ), f"Expected with_broker with {broker}"
