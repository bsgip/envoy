import pytest

from envoy.server.request_state import RequestStateParameters


def test_RequestStateParameters_invalid_definition():
    with pytest.raises(ValueError):
        RequestStateParameters(aggregator_id=1, site_id=2, lfdi="a", sfdi=1, href_prefix="a/b")

    # No errors
    RequestStateParameters(aggregator_id=None, site_id=2, lfdi="a", sfdi=1, href_prefix="a/b")
    RequestStateParameters(aggregator_id=1, site_id=None, lfdi="a", sfdi=1, href_prefix="a/b")
    RequestStateParameters(aggregator_id=None, site_id=None, lfdi="a", sfdi=1, href_prefix="a/b")
