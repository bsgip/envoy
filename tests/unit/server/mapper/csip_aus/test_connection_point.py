from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointResponse

from envoy.server.mapper.csip_aus.connection_point import ConnectionPointMapper
from envoy.server.model.site import Site
from tests.data.fake.generator import generate_class_instance


def test_map_to_response():
    """Simple sanity check on the mapper to ensure things don't break with a variety of values."""
    site_all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    site_optional: Site = generate_class_instance(Site, seed=202, optional_is_none=True)

    result_all_set = ConnectionPointMapper.map_to_response(site_all_set)
    assert result_all_set is not None
    assert isinstance(result_all_set, ConnectionPointResponse)
    assert result_all_set.id == site_all_set.nmi

    result_optional = ConnectionPointMapper.map_to_response(site_optional)
    assert result_optional is not None
    assert isinstance(result_optional, ConnectionPointResponse)
    assert result_optional.id == "", "None NMI maps to empty string"
