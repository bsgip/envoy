from itertools import product
from typing import Optional

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.log_events import LogEvent, LogEventList

from envoy.server.mapper.sep2.log_event import LogEventListMapper, LogEventMapper
from envoy.server.model.site import SiteLogEvent
from envoy.server.request_scope import BaseRequestScope, DeviceOrAggregatorRequestScope


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_log_event_round_trip(optional_is_none: bool):
    site_id = 123321
    scope = generate_class_instance(BaseRequestScope, seed=101, optional_is_none=optional_is_none)
    original = generate_class_instance(SiteLogEvent, seed=202, optional_is_none=optional_is_none, site_id=site_id)

    mapped = LogEventMapper.map_to_log_event(scope, original)
    actual = LogEventMapper.map_from_log_event(mapped, site_id)

    assert isinstance(actual, SiteLogEvent)
    assert_class_instance_equality(
        SiteLogEvent, original, actual, ignored_properties={"site_log_event_id", "created_time"}
    )
    assert actual.site_log_event_id is None, "site_log_event_id should be left unset (the DB sets it)"
    assert actual.created_time is None, "created_time should be left unset (the DB sets it)"


@pytest.mark.parametrize("href_prefix, optional_is_none", product([None, "/my/href/prefix/"], [True, False]))
def test_map_to_log_event_response(href_prefix: Optional[str], optional_is_none: bool):
    """Sanity checks that we generate valid models and avoid runtime errors"""
    # Arrange
    scope = generate_class_instance(BaseRequestScope, optional_is_none=optional_is_none, href_prefix=href_prefix)
    site_log_event = generate_class_instance(SiteLogEvent, seed=202, optional_is_none=optional_is_none)

    # Act
    result = LogEventMapper.map_to_log_event(scope, site_log_event)

    # Assert
    assert isinstance(result, LogEvent)
    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
    assert result.logEventCode == site_log_event.log_event_code
    assert result.logEventID == site_log_event.log_event_id
    assert result.functionSet == site_log_event.function_set


@pytest.mark.parametrize("optional_is_none", product([True, False]))
def test_map_from_log_event_request(optional_is_none: bool):
    site_id = 123541
    log_event = generate_class_instance(LogEvent, seed=101, optional_is_none=optional_is_none)

    result = LogEventMapper.map_from_log_event(log_event, site_id)
    assert isinstance(result, SiteLogEvent)
    assert result.site_log_event_id is None, "Assigned by the database"
    assert result.created_time is None, "Assigned by the database"
    assert result.site_id == site_id
    assert result.function_set == log_event.functionSet
    assert result.profile_id == log_event.profileID
    assert result.extended_data == log_event.extendedData
    assert result.details == log_event.details


@pytest.mark.parametrize(
    "href_prefix, optional_is_none, response_count", product([None, "/my/href/prefix/"], [True, False], [0, 2])
)
def test_map_to_list_response(href_prefix: Optional[str], optional_is_none: bool, response_count: int):
    """Attempts to trip up the list mappers with a runtime error for various input combinations"""

    # Arrange
    display_site_id = 87618732141
    scope = generate_class_instance(
        DeviceOrAggregatorRequestScope,
        optional_is_none=optional_is_none,
        href_prefix=href_prefix,
        display_site_id=display_site_id,
    )
    responses: list[SiteLogEvent] = [
        generate_class_instance(SiteLogEvent, seed=101 * (i + 1), optional_is_none=optional_is_none)
        for i in range(response_count)
    ]
    total_responses = 15125

    # Act
    result = LogEventListMapper.map_to_list_response(scope, responses, total_responses)

    # Assert
    assert isinstance(result, LogEventList)
    assert_list_type(LogEvent, result.LogEvent_, count=response_count)
    assert result.all_ == total_responses
    assert result.results == response_count
    if href_prefix is not None:
        assert result.href.startswith(href_prefix)
    assert str(display_site_id) in result.href
