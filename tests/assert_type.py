from typing import Any, Optional, get_origin


def assert_list_type(expected_element_type: type, obj: Any, count: Optional[int] = None):
    """Asserts that obj is not None, is a list and every element is expected_element_type

    if count is specified - an additional assert will be made on the count of elements in obj"""
    assert obj is not None
    assert (
        isinstance(obj, list) or get_origin(type(obj)) == list
    ), f"Expected a list type for obj but got {type(obj)} instead"
    assert_iterable_type(expected_element_type, obj, count=count)


def assert_iterable_type(expected_element_type: type, obj: Any, count: Optional[int] = None):
    """Asserts that obj is not None, is iterable and every element is expected_element_type

    if count is specified - an additional assert will be made on the count of elements in obj"""
    assert obj is not None

    try:
        iter(obj)
    except TypeError as ex:
        assert False, f"Expected {type(obj)} to be iterable but calling iter(obj) raises {ex}"

    for i, val in enumerate(obj):
        assert isinstance(
            val, expected_element_type
        ), f"obj[{i}]: Element has type {type(val)} instead of {expected_element_type}"

    if count is not None:
        assert len(obj) == count
