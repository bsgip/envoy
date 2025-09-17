from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse

from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.model.site import Site
from envoy.server.request_scope import BaseRequestScope


def test_map_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""

    scope_all_set = generate_class_instance(BaseRequestScope, href_prefix="/my/prefix")
    site_all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)

    scope_optional = generate_class_instance(BaseRequestScope, href_prefix=None)
    site_optional: Site = generate_class_instance(Site, seed=202, optional_is_none=True)

    result_all_set = ConnectionPointMapper.map_to_response(scope_all_set, site_all_set)
    assert result_all_set is not None
    assert isinstance(result_all_set, ConnectionPointResponse)
    assert result_all_set.id == site_all_set.nmi
    assert result_all_set.href.startswith("/my/prefix")
    assert f"/{site_all_set.site_id}/" in result_all_set.href

    result_optional = ConnectionPointMapper.map_to_response(scope_optional, site_optional)
    assert result_optional is not None
    assert isinstance(result_optional, ConnectionPointResponse)
    assert result_optional.id == "", "None NMI maps to empty string"
    assert f"/{site_optional.site_id}/" in result_optional.href
