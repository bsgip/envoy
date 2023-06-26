from envoy.admin.mapper.site import SiteMapper
from envoy.admin.schema.site import SitePageResponse, SiteResponse
from envoy.server.model.site import Site
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


def test_site_single_entity_mapper():
    all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    with_none: Site = generate_class_instance(Site, seed=202, optional_is_none=True)

    all_set_mapped = SiteMapper.map_to_site_response(all_set)
    with_none_mapped = SiteMapper.map_to_site_response(with_none)

    assert isinstance(all_set_mapped, SiteResponse)
    assert isinstance(with_none_mapped, SiteResponse)

    # we can get away with check_class_instance_equality as the field names are all the same
    assert_class_instance_equality(SiteResponse, all_set, all_set_mapped)
    assert_class_instance_equality(SiteResponse, with_none, with_none_mapped)


def test_site_page_mapper():
    sites: list[Site] = [
        generate_class_instance(Site, seed=1001, optional_is_none=False, generate_relationships=False),
        generate_class_instance(Site, seed=2002, optional_is_none=True, generate_relationships=False),
        generate_class_instance(Site, seed=1001, optional_is_none=False, generate_relationships=True),
        generate_class_instance(Site, seed=2002, optional_is_none=True, generate_relationships=True),
    ]
    count = 123
    limit = 456
    start = 789

    mapped = SiteMapper.map_to_response(count, limit, start, sites)
    assert isinstance(mapped, SitePageResponse)

    assert mapped.total_count == count
    assert mapped.limit == limit
    assert mapped.start == start
    assert len(sites) == len(mapped.sites)
    assert all([isinstance(s, SiteResponse) for s in mapped.sites])
