import re

from envoy.server.mapper.sep2.mrid import ResponseSetType
from envoy.server.mapper.sep2.response import response_set_type_to_href


def test_response_set_type_to_href():
    """Ensure all calls to response_set_type_to_href generate unique values"""
    hrefs = []
    for response_set_type in ResponseSetType:
        href = response_set_type_to_href(response_set_type)
        assert isinstance(href, str)
        assert re.match("[^a-z0-9]", href) is None, "href slug should just be alphanumeric"
        assert href == response_set_type_to_href(response_set_type), "Value should be stable"
        hrefs.append(href)

    assert len(hrefs) > 0
    assert len(hrefs) == len(set(hrefs)), "All values should be unique"


def test_not_implemented_yet():
    raise NotImplementedError()
