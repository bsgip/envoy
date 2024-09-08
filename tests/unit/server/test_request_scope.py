from typing import Optional, Union

import pytest
from fastapi import HTTPException

from envoy.server.crud.end_device import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.request_scope import AggregatorRequestScope, RawRequestScope, SiteRequestScope


@pytest.mark.parametrize(
    "raw_scope, requested_site_id, expected",
    [
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            22,
            AggregatorRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22, 22),
        ),  # Site scoped request trying to get to that site
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            2,
            HTTPException,
        ),  # Site is trying to access site 2 but it's scoped to site 22
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            None,
            HTTPException,
        ),  # Site is trying to get unscoped site access but it's scoped to site 22
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            VIRTUAL_END_DEVICE_SITE_ID,
            HTTPException,
        ),  # Site is trying to get unscoped site access but it's scoped to site 22
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, None),
            2,
            AggregatorRequestScope("lfdi_val", 1234, "/my/prefix", 11, 2, 2),
        ),  # Site is trying to access site 2 and has no site scope restrictions
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, None),
            VIRTUAL_END_DEVICE_SITE_ID,
            AggregatorRequestScope("lfdi_val", 1234, "/my/prefix", 11, VIRTUAL_END_DEVICE_SITE_ID, None),
        ),  # Site is trying to access all devices for an aggregator (and has permission to)
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, None),
            None,
            AggregatorRequestScope("lfdi_val", 1234, "/my/prefix", 11, VIRTUAL_END_DEVICE_SITE_ID, None),
        ),  # Site is trying to access all devices for an aggregator  (and has permission to)
    ],
)
def test_RawRequestScope_to_aggregator_request_scope(
    raw_scope: RawRequestScope, requested_site_id: Optional[int], expected: Union[AggregatorRequestScope, type]
):

    if isinstance(expected, type):
        with pytest.raises(expected):
            raw_scope.to_aggregator_request_scope(requested_site_id)

    else:
        actual = raw_scope.to_aggregator_request_scope(requested_site_id)
        assert isinstance(actual, AggregatorRequestScope)
        assert not isinstance(actual, SiteRequestScope)
        assert actual == expected


@pytest.mark.parametrize(
    "raw_scope, requested_site_id, expected",
    [
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            22,
            SiteRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22, 22),
        ),  # Site scoped request trying to get to that site
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            2,
            HTTPException,
        ),  # Site is trying to access site 2 but it's scoped to site 22
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, 22),
            VIRTUAL_END_DEVICE_SITE_ID,
            HTTPException,
        ),  # Site is trying to get unscoped site access but it's scoped to site 22
        (
            RawRequestScope("lfdi_val", 1235, "/my/prefix", 11, None),
            2,
            SiteRequestScope("lfdi_val", 1235, "/my/prefix", 11, 2, 2),
        ),  # Site is trying to access site 2 and has no site scope restrictions
        (
            RawRequestScope("lfdi_val", 1234, "/my/prefix", 11, None),
            VIRTUAL_END_DEVICE_SITE_ID,
            HTTPException,
        ),  # Can't access aggregator end device in a site request scope
    ],
)
def test_RawRequestScope_to_site_request_scope(
    raw_scope: RawRequestScope, requested_site_id: Optional[int], expected: Union[SiteRequestScope, type]
):

    if isinstance(expected, type):
        with pytest.raises(expected):
            raw_scope.to_site_request_scope(requested_site_id)

    else:
        actual = raw_scope.to_site_request_scope(requested_site_id)
        assert isinstance(actual, SiteRequestScope)
        assert actual == expected
