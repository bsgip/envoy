from datetime import datetime
from decimal import Decimal
from itertools import product
from typing import Optional, get_type_hints

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import CLASS_MEMBER_FETCHERS, generate_class_instance, get_generatable_class_base
from envoy_schema.admin.schema.site import DERAvailability, DERConfiguration, DERStatus
from envoy_schema.admin.schema.site import SiteGroup as AdminSiteGroup
from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse

from envoy.admin.mapper.site import SiteGroupMapper, SiteMapper
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus, SiteGroup


def test_map_to_der_availability_response():
    """Mainly a quick sanity check"""
    with_optionals = generate_class_instance(SiteDERAvailability, seed=101, optional_is_none=True)
    all_set = generate_class_instance(SiteDERAvailability, seed=202, optional_is_none=False)

    assert SiteMapper.map_to_der_availability_response(None) is None

    mapped_optionals = SiteMapper.map_to_der_availability_response(with_optionals)
    assert isinstance(mapped_optionals, DERAvailability)

    mapped_all_set = SiteMapper.map_to_der_availability_response(all_set)
    assert isinstance(mapped_all_set, DERAvailability)


def test_map_to_der_status_response():
    """Mainly a quick sanity check"""
    with_optionals = generate_class_instance(SiteDERStatus, seed=101, optional_is_none=True)
    all_set = generate_class_instance(SiteDERStatus, seed=202, optional_is_none=False)

    assert SiteMapper.map_to_der_status_response(None) is None

    mapped_optionals = SiteMapper.map_to_der_status_response(with_optionals)
    assert isinstance(mapped_optionals, DERStatus)

    mapped_all_set = SiteMapper.map_to_der_status_response(all_set)
    assert isinstance(mapped_all_set, DERStatus)


@pytest.mark.parametrize(
    "setting, rating",
    product(
        [
            None,
            generate_class_instance(SiteDERSetting, seed=101, optional_is_none=True),
            generate_class_instance(SiteDERSetting, seed=202, optional_is_none=False),
        ],
        [
            None,
            generate_class_instance(SiteDERRating, seed=303, optional_is_none=True),
            generate_class_instance(SiteDERRating, seed=404, optional_is_none=False),
        ],
    ),
)
def test_map_to_der_config_response_no_bad_combinations(
    setting: Optional[SiteDERSetting], rating: Optional[SiteDERRating]
):
    """The failover logic for map_to_der_config_response can be a little finnicky - this is just trying
    to catch any potential slipups in the definitions"""
    cfg = SiteMapper.map_to_der_config_response(rating, setting)
    if setting is None and rating is None:
        assert cfg is None
    else:
        assert isinstance(cfg, DERConfiguration)


def get_attrs_for_type(base_type: type) -> list[tuple[str, type]]:
    type_hints = get_type_hints(base_type)
    results: list[tuple[str, type]] = []
    for name in CLASS_MEMBER_FETCHERS[get_generatable_class_base(base_type)](base_type):
        t = type_hints.get(name, None)
        if t is not None:
            results.append((name, t))
    return results


@pytest.mark.parametrize(
    "attr_name, attr_type",
    [(n, t) for (n, t) in get_attrs_for_type(DERConfiguration) if t == Optional[Decimal]],
)
def test_map_to_der_config_response_optional_decimal_failovers(attr_name, attr_type):
    """Tests that the decimal values in DERConfiguration get correctly mapped depending on whether setting/rating
    is specified. This runs through a bunch of combos (per attribute) that attempt to pickup any particular case
    where the failover is not working"""

    setting: SiteDERSetting = generate_class_instance(SiteDERSetting, seed=202, optional_is_none=False)
    rating: SiteDERRating = generate_class_instance(SiteDERRating, seed=404, optional_is_none=False)
    all_values: list[Decimal] = []
    for rating_value, rating_multiplier, setting_value, setting_multiplier in [
        (None, None, None, None),
        (None, None, 1, 1),
        (None, None, 1, 2),
        (None, None, 2, 1),
        (3, 3, None, None),
        (3, 4, None, None),
        (4, 3, None, None),
        (3, 3, 5, 5),
        (3, 3, 5, 6),
        (3, 3, 6, 5),
    ]:
        setattr(setting, attr_name + "_value", setting_value)
        setattr(setting, attr_name + "_multiplier", setting_multiplier)
        setattr(rating, attr_name + "_value", rating_value)
        setattr(rating, attr_name + "_multiplier", rating_multiplier)

        mapped = SiteMapper.map_to_der_config_response(rating, setting)
        value = getattr(mapped, attr_name)
        if value is None:
            value = Decimal(0)

        all_values.append(value)

    assert len(all_values) == len(
        set(all_values)
    ), "Expected all generated values to be unique (are the failovers working?)"


def test_site_single_entity_mapper():
    all_set: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    with_none: Site = generate_class_instance(Site, seed=202, optional_is_none=True)
    with_groups_and_der: Site = generate_class_instance(
        Site, seed=303, optional_is_none=False, generate_relationships=True
    )
    assert len(with_groups_and_der.assignments) > 0, "Expecting at least 1 group"
    assert len(with_groups_and_der.site_ders) > 0, "Expecting at least 1 der"

    all_set_mapped = SiteMapper.map_to_site_response(all_set)
    with_none_mapped = SiteMapper.map_to_site_response(with_none)
    with_groups_der_mapped = SiteMapper.map_to_site_response(with_groups_and_der)

    assert isinstance(all_set_mapped, SiteResponse)
    assert isinstance(with_none_mapped, SiteResponse)
    assert isinstance(with_groups_der_mapped, SiteResponse)

    # we can get away with check_class_instance_equality as the field names are all the same
    assert_class_instance_equality(SiteResponse, all_set, all_set_mapped)
    assert_class_instance_equality(SiteResponse, with_none, with_none_mapped)
    assert_class_instance_equality(SiteResponse, with_groups_and_der, with_groups_der_mapped)

    assert len(all_set_mapped.groups) == 0, "No groups on this type"
    assert len(with_none_mapped.groups) == 0, "No groups on this type"
    assert len(with_groups_der_mapped.groups) == len(with_groups_and_der.assignments)

    # Validating each of the groups maps back to the original group
    # we can get away with check_class_instance_equality as the field names are all the same
    for exp, act in zip(with_groups_and_der.assignments, with_groups_der_mapped.groups):
        assert_class_instance_equality(AdminSiteGroup, exp.group, act)

    assert isinstance(with_groups_der_mapped.der_availability, DERAvailability)
    assert isinstance(with_groups_der_mapped.der_config, DERConfiguration)
    assert isinstance(with_groups_der_mapped.der_status, DERStatus)

    assert all_set_mapped.der_availability is None
    assert all_set_mapped.der_config is None
    assert all_set_mapped.der_status is None


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
    after = datetime(2022, 5, 6, 7, 8, 9)
    group_filter = "abc-123"

    mapped = SiteMapper.map_to_response(count, limit, start, group_filter, after, sites)
    assert isinstance(mapped, SitePageResponse)

    assert mapped.total_count == count
    assert mapped.limit == limit
    assert mapped.start == start
    assert mapped.after == after
    assert mapped.group == group_filter
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
