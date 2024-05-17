from envoy_schema.admin.schema.site import SiteGroup as AdminSiteGroup
from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse

from envoy.admin.mapper.site import SiteGroupMapper, SiteMapper
from envoy.server.model.site import Site, SiteGroup
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


def test_site_single_entity_mapper():
    all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    with_none: Site = generate_class_instance(Site, seed=202, optional_is_none=True)
    with_groups: Site = generate_class_instance(Site, seed=303, optional_is_none=False, generate_relationships=True)
    assert len(with_groups.assignments) > 0, "Expecting at least 1 group"

    all_set_mapped = SiteMapper.map_to_site_response(all_set)
    with_none_mapped = SiteMapper.map_to_site_response(with_none)
    with_groups_mapped = SiteMapper.map_to_site_response(with_groups)

    assert isinstance(all_set_mapped, SiteResponse)
    assert isinstance(with_none_mapped, SiteResponse)
    assert isinstance(with_groups_mapped, SiteResponse)

    # we can get away with check_class_instance_equality as the field names are all the same
    assert_class_instance_equality(SiteResponse, all_set, all_set_mapped)
    assert_class_instance_equality(SiteResponse, with_none, with_none_mapped)
    assert_class_instance_equality(SiteResponse, with_groups, with_groups_mapped)

    assert len(all_set_mapped.groups) == 0, "No groups on this type"
    assert len(with_none_mapped.groups) == 0, "No groups on this type"
    assert len(with_groups_mapped.groups) == len(with_groups.assignments)

    # Validating each of the groups maps back to the original group
    # we can get away with check_class_instance_equality as the field names are all the same
    for exp, act in zip(with_groups.assignments, with_groups_mapped.groups):
        assert_class_instance_equality(AdminSiteGroup, exp.group, act)


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


def test_site_group_single_entity_mapper():
    all_set: SiteGroup = generate_class_instance(SiteGroup, seed=101, optional_is_none=False)
    with_none: SiteGroup = generate_class_instance(SiteGroup, seed=202, optional_is_none=True)

    all_set_mapped = SiteGroupMapper.map_to_site_group_response(all_set, 123)
    with_none_mapped = SiteGroupMapper.map_to_site_group_response(with_none, 456)

    assert isinstance(all_set_mapped, SiteGroupResponse)
    assert isinstance(with_none_mapped, SiteGroupResponse)

    # we can get away with check_class_instance_equality as the field names are all the same
    assert_class_instance_equality(SiteGroupResponse, all_set, all_set_mapped, ignored_properties=set(["total_sites"]))
    assert all_set_mapped.total_sites == 123
    assert_class_instance_equality(
        SiteGroupResponse, with_none, with_none_mapped, ignored_properties=set(["total_sites"])
    )
    assert with_none_mapped.total_sites == 456


def test_site_group_page_mapper():
    groups: list[tuple[SiteGroup, int]] = [
        (generate_class_instance(SiteGroup, seed=1001, optional_is_none=False, generate_relationships=False), 11),
        (generate_class_instance(SiteGroup, seed=2002, optional_is_none=True, generate_relationships=False), 22),
        (generate_class_instance(SiteGroup, seed=1001, optional_is_none=False, generate_relationships=True), 33),
        (generate_class_instance(SiteGroup, seed=2002, optional_is_none=True, generate_relationships=True), 44),
    ]
    count = 123
    limit = 456
    start = 789

    mapped = SiteGroupMapper.map_to_response(count, limit, start, groups)
    assert isinstance(mapped, SiteGroupPageResponse)

    assert mapped.total_count == count
    assert mapped.limit == limit
    assert mapped.start == start
    assert len(groups) == len(mapped.groups)
    assert all([isinstance(s, SiteGroupResponse) for s in mapped.groups])
    assert [s.total_sites for s in mapped.groups] == [c for _, c in groups]
