from datetime import datetime
from itertools import product
from typing import Optional, Union, cast

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.der import DERControlResponse
from envoy_schema.server.schema.sep2.end_device import EndDeviceResponse
from envoy_schema.server.schema.sep2.metering import Reading
from envoy_schema.server.schema.sep2.pricing import TimeTariffIntervalResponse
from envoy_schema.server.schema.sep2.pub_sub import (
    XSI_TYPE_DER_AVAILABILITY,
    XSI_TYPE_DER_CAPABILITY,
    XSI_TYPE_DER_CONTROL_LIST,
    XSI_TYPE_DER_SETTINGS,
    XSI_TYPE_DER_STATUS,
    XSI_TYPE_END_DEVICE_LIST,
    XSI_TYPE_READING_LIST,
    XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
)
from envoy_schema.server.schema.sep2.pub_sub import Condition as Sep2Condition
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier, Notification
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionListResponse
from envoy_schema.server.schema.uri import (
    DERAvailabilityUri,
    DERCapabilityUri,
    DERControlListUri,
    DERSettingsUri,
    DERStatusUri,
    EndDeviceListUri,
)

from envoy.server.crud.end_device import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID
from envoy.server.mapper.sep2.der import to_hex_binary
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.mapper.sep2.pub_sub import NotificationMapper, SubscriptionListMapper, SubscriptionMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import DeviceOrAggregatorRequestScope, SiteRequestScope


def assert_entity_hrefs_contain_entity_id_and_prefix(
    hrefs: list[str], expected_site_ids: list[int], expected_prefix: str
):
    """Given a list of hrefs for entities inside of a notification - check that they all contain certain site ids and
    have an expected prefix.

    hrefs and expected_site_ids are expected to have 1-1 correspondence

    eg:
      ["/edev/1/cp", "/edev/2/cp"], [1, 2] would pass
      ["/edev/1/cp", "/edev/2/cp"], [1, 3] would fail
      ["/edev/1/cp", "/edev/2/cp"], [2, 1] would fail
    """
    assert len(hrefs) == len(expected_site_ids), "If this fails, its a misconfigured test"

    for href, expected_site_id in zip(hrefs, expected_site_ids):
        assert f"/{expected_site_id}" in href
        assert href.startswith(expected_prefix)


@pytest.mark.parametrize("resource", list(SubscriptionResource))
def test_SubscriptionMapper_calculate_resource_href_at_least_one_supported_combo(resource: SubscriptionResource):
    """Validates the various SubscriptionResource values should have at least 1 supported combo of site/resource id"""
    display_site_id = 2518761283
    hrefs: list[str] = []
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=display_site_id, href_prefix="/foo/bar"
    )
    for site_id, resource_id in product([1, None], [2, None]):
        sub: Subscription = generate_class_instance(Subscription)
        sub.resource_type = resource
        sub.scoped_site_id = site_id
        sub.resource_id = resource_id

        try:
            href = SubscriptionMapper.calculate_resource_href(sub, scope)
            assert href and isinstance(href, str)
            assert href.startswith(scope.href_prefix)
            if resource != SubscriptionResource.SITE:
                assert f"/{display_site_id}" in href, "Validating the display_site_id is being used over site_id"

            hrefs.append(href)
        except InvalidMappingError:
            pass

    assert len(hrefs) > 0, f"Expected at least one combo of site/resource ID to generate a validate href for {resource}"


@pytest.mark.parametrize("resource", list(SubscriptionResource))
def test_SubscriptionMapper_calculate_resource_href_all_support_site_unscoped(resource: SubscriptionResource):
    """Validates the various SubscriptionResource values should have at least 1 supported combo of unscoped site and
    either a specified resource id or none"""

    hrefs: list[str] = []
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, optional_is_none=True
    )
    for resource_id in [1, None]:
        sub: Subscription = generate_class_instance(Subscription)
        sub.resource_type = resource
        sub.scoped_site_id = None
        sub.resource_id = resource_id

        try:
            href = SubscriptionMapper.calculate_resource_href(sub, scope)
            assert href and isinstance(href, str)
            hrefs.append(href)
        except InvalidMappingError:
            pass

    assert (
        len(hrefs) > 0
    ), f"Expected at least one combo of unscoped site/resource ID to generate a validate href for {resource}"


@pytest.mark.parametrize(
    "site_id, resource", product([999, None], [r for r in list(SubscriptionResource) if r != SubscriptionResource.SITE])
)
def test_SubscriptionMapper_calculate_resource_href_encodes_site_id(
    site_id: Optional[int], resource: SubscriptionResource
):

    display_site_id = VIRTUAL_END_DEVICE_SITE_ID if site_id is None else site_id
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, display_site_id=display_site_id
    )

    sub: Subscription = generate_class_instance(Subscription)
    sub.resource_type = resource
    sub.scoped_site_id = 8912491  # We want to ignore this value and use the display_site_id from the scope
    sub.resource_id = None

    try:
        href = SubscriptionMapper.calculate_resource_href(sub, scope)
    except InvalidMappingError:
        sub.resource_id = 888
        href = SubscriptionMapper.calculate_resource_href(sub, scope)

    assert f"/{scope.display_site_id}" in href, "Expected display site id in href"


@pytest.mark.parametrize("resource, site_id, resource_id", product(SubscriptionResource, [1, None], [2, None]))
def test_SubscriptionMapper_calculate_resource_href_uses_prefix(
    resource: SubscriptionResource, site_id: Optional[int], resource_id: Optional[int]
):
    """Validates the various inputs/expected outputs apply the href_prefix"""
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope, href_prefix=None)
    sub: Subscription = generate_class_instance(Subscription)
    sub.resource_type = resource
    sub.scoped_site_id = site_id
    sub.resource_id = resource_id

    # set output to None if we hit an unsupported combo of inputs
    href_no_prefix: Optional[str]
    try:
        href_no_prefix = SubscriptionMapper.calculate_resource_href(sub, scope)
        assert href_no_prefix
    except InvalidMappingError:
        href_no_prefix = None

    # set output to None if we hit an unsupported combo of inputs
    prefix = "/my/prefix/for/tests"
    scope_prefix: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, href_prefix=prefix
    )
    href_with_prefix: Optional[str]
    try:
        href_with_prefix = SubscriptionMapper.calculate_resource_href(sub, scope_prefix)
        assert href_with_prefix
    except InvalidMappingError:
        href_with_prefix = None

    if href_with_prefix is None or href_no_prefix is None:
        assert (
            href_with_prefix is None and href_no_prefix is None
        ), "If prefix raises InvalidMappingError - so must no prefix"
    else:
        # The hrefs should be identical (sans prefix)
        assert href_with_prefix.startswith(prefix)
        assert not href_no_prefix.startswith(prefix)
        assert href_with_prefix == generate_href(href_no_prefix, scope_prefix)


def test_SubscriptionMapper_calculate_resource_href_bad_type():
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope)
    sub: Subscription = generate_class_instance(Subscription)
    sub.resource_type = 9876  # invalid type
    with pytest.raises(InvalidMappingError):
        SubscriptionMapper.calculate_resource_href(sub, scope)


def test_SubscriptionMapper_calculate_resource_href_unique_hrefs():
    """Validates the various inputs/expected outputs apply the href_prefix"""
    sub: Subscription = generate_class_instance(Subscription)

    all_hrefs: list[str] = []
    total_fails = 0

    # We filter out the only "non unique" case which is SITE where resource_id has a value (it's nonsensical)
    unique_combos = [
        c
        for c in product(SubscriptionResource, [1, None], [2, None])
        if c != (SubscriptionResource.SITE, 1, 2) and c != (SubscriptionResource.SITE, None, 2)
    ]

    for resource, site_id, resource_id in unique_combos:

        display_site_id = VIRTUAL_END_DEVICE_SITE_ID if site_id is None else site_id
        scope: DeviceOrAggregatorRequestScope = generate_class_instance(
            DeviceOrAggregatorRequestScope, display_site_id=display_site_id, site_id=site_id
        )

        sub.resource_type = resource
        sub.scoped_site_id = display_site_id + 999  # Ensure this isn't considered for href creation
        sub.resource_id = resource_id

        try:
            href = SubscriptionMapper.calculate_resource_href(sub, scope)
        except InvalidMappingError:
            total_fails = total_fails + 1
            continue

        assert href and isinstance(href, str)
        all_hrefs.append(href)

        if site_id is not None:
            assert str(site_id) in href, "If the ID is specified - it should be in the generated href"

        if resource_id is not None:
            assert str(resource_id) in href, "If the ID is specified - it should be in the generated href"

    assert len(all_hrefs) == len(set(all_hrefs)), f"Expected all hrefs to be unique: {all_hrefs}"
    assert total_fails < 25, "There shouldn't be this many combinations generating InvalidMappingError - go investigate"


def test_SubscriptionMapper_map_to_response_condition():
    cond_all_set: SubscriptionCondition = generate_class_instance(
        SubscriptionCondition, seed=101, optional_is_none=False
    )
    cond_all_set.attribute = ConditionAttributeIdentifier.READING_VALUE

    sep2_cond_all_set = SubscriptionMapper.map_to_response_condition(cond_all_set)
    assert isinstance(sep2_cond_all_set, Sep2Condition)
    assert sep2_cond_all_set.lowerThreshold == cond_all_set.lower_threshold
    assert sep2_cond_all_set.upperThreshold == cond_all_set.upper_threshold

    # Ensure we dont end up exceptions
    cond_optional: SubscriptionCondition = generate_class_instance(
        SubscriptionCondition, seed=101, optional_is_none=True
    )
    cond_optional.attribute = ConditionAttributeIdentifier.READING_VALUE
    sep2_cond_optional = SubscriptionMapper.map_to_response_condition(cond_optional)
    assert isinstance(sep2_cond_optional, Sep2Condition)


def test_SubscriptionMapper_map_to_response():
    sub_all_set: Subscription = generate_class_instance(Subscription, seed=101, optional_is_none=False)
    sub_all_set.conditions = []
    sub_all_set.notification_uri = "http://my.example:11/foo"
    sub_all_set.resource_type = SubscriptionResource.READING
    sub_optional: Subscription = generate_class_instance(Subscription, seed=101, optional_is_none=True)
    sub_optional.conditions = []
    sub_optional.notification_uri = "https://my.example:22/foo"
    sub_optional.resource_type = SubscriptionResource.SITE
    sub_with_condition: Subscription = generate_class_instance(Subscription, seed=101, optional_is_none=True)
    sub_with_condition.conditions = [cast(SubscriptionCondition, generate_class_instance(SubscriptionCondition))]
    sub_with_condition.conditions[0].attribute = ConditionAttributeIdentifier.READING_VALUE
    sub_with_condition.notification_uri = "http://my.example:33/foo"
    sub_with_condition.resource_type = SubscriptionResource.SITE

    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope, href_prefix=None)
    scope_prefix: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, href_prefix="/my/prefix"
    )

    # check prefix is applied
    sep2_prefix = SubscriptionMapper.map_to_response(sub_all_set, scope_prefix)
    assert sep2_prefix.href and isinstance(sep2_prefix.href, str)
    assert sep2_prefix.href.startswith(scope_prefix.href_prefix)
    assert sep2_prefix.subscribedResource and isinstance(sep2_prefix.subscribedResource, str)
    assert sep2_prefix.subscribedResource.startswith(scope_prefix.href_prefix)
    assert scope_prefix.href_prefix not in sep2_prefix.notificationURI

    # Check a boring sub
    sep2_all_set = SubscriptionMapper.map_to_response(sub_all_set, scope)
    assert isinstance(sep2_all_set, Sep2Subscription)
    assert sep2_all_set.condition is None
    assert sep2_all_set.href and isinstance(sep2_all_set.href, str)
    assert sep2_all_set.subscribedResource and isinstance(sep2_all_set.subscribedResource, str)
    assert sep2_all_set.notificationURI == sub_all_set.notification_uri
    assert sep2_all_set.limit == sub_all_set.entity_limit

    sep2_optional = SubscriptionMapper.map_to_response(sub_optional, scope)
    assert isinstance(sep2_optional, Sep2Subscription)
    assert sep2_optional.condition is None
    assert sep2_optional.href and isinstance(sep2_optional.href, str)
    assert sep2_optional.subscribedResource and isinstance(sep2_optional.subscribedResource, str)
    assert sep2_optional.notificationURI == sub_optional.notification_uri
    assert sep2_optional.limit == sub_optional.entity_limit

    sep2_condition = SubscriptionMapper.map_to_response(sub_with_condition, scope)
    assert isinstance(sep2_condition, Sep2Subscription)
    assert isinstance(sep2_condition.condition, Sep2Condition)
    assert sep2_condition.href and isinstance(sep2_condition.href, str)
    assert sep2_condition.subscribedResource and isinstance(sep2_condition.subscribedResource, str)
    assert sep2_condition.notificationURI == sub_with_condition.notification_uri
    assert sep2_condition.limit == sub_with_condition.entity_limit


def test_SubscriptionListMapper_map_to_site_response():
    sub_list: list[Subscription] = [
        generate_class_instance(Subscription, seed=101, optional_is_none=False),
        generate_class_instance(Subscription, seed=202, optional_is_none=True),
    ]
    sub_list[0].notification_uri = "http://my.example:11/foo"
    sub_list[0].resource_type = SubscriptionResource.TARIFF_GENERATED_RATE
    sub_list[1].notification_uri = "https://my.example:22/bar"
    sub_list[1].resource_type = SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE
    sub_list[1].scoped_site_id = 1
    sub_count = 43
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, optional_is_none=True, href_prefix="/custom/prefix"
    )

    mapped = SubscriptionListMapper.map_to_site_response(scope, sub_list, sub_count)

    assert isinstance(mapped, SubscriptionListResponse)
    assert str(scope.display_site_id) in mapped.href
    assert mapped.results == len(sub_list)
    assert mapped.all_ == sub_count
    assert_list_type(Sep2Subscription, mapped.subscriptions, count=len(sub_list))


def test_SubscriptionMapper_calculate_subscription_href():
    """Validates that the hrefs don't raise errors and vary depending on inputs"""
    # Using the same keys -
    sub_all_set = generate_class_instance(Subscription, seed=101, optional_is_none=False)
    sub_optional = generate_class_instance(Subscription, seed=101, optional_is_none=True)

    scope: DeviceOrAggregatorRequestScope = generate_class_instance(DeviceOrAggregatorRequestScope, href_prefix=None)
    scope_prefix: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, href_prefix="/my/prefix"
    )

    # Subscriptions scoped to a EndDevice are different to those that are "global"
    assert SubscriptionMapper.calculate_subscription_href(
        sub_all_set, scope
    ) != SubscriptionMapper.calculate_subscription_href(sub_optional, scope_prefix)
    assert SubscriptionMapper.calculate_subscription_href(
        sub_all_set, scope
    ) != SubscriptionMapper.calculate_subscription_href(sub_optional, scope_prefix)

    # The href_prefix is included
    assert SubscriptionMapper.calculate_subscription_href(
        sub_all_set, scope
    ) != SubscriptionMapper.calculate_subscription_href(sub_all_set, scope_prefix)
    assert SubscriptionMapper.calculate_subscription_href(
        sub_optional, scope
    ) != SubscriptionMapper.calculate_subscription_href(sub_optional, scope_prefix)


def test_SubscriptionMapper_map_from_request():

    # Using the same keys -
    sub_all_set: Sep2Subscription = generate_class_instance(Sep2Subscription, seed=101, optional_is_none=False)
    sub_all_set.subscribedResource = "/prefix/edev/123"
    sub_all_set.notificationURI = "https://foo.bar:44/path"
    sub_optional: Sep2Subscription = generate_class_instance(Sep2Subscription, seed=202, optional_is_none=True)
    sub_optional.subscribedResource = "/prefix/edev/123"
    sub_optional.notificationURI = "https://foo.bar:44/path"
    sub_condition: Sep2Subscription = generate_class_instance(Sep2Subscription, seed=303, optional_is_none=False)
    sub_condition.subscribedResource = "/prefix/edev/123"
    sub_condition.notificationURI = "https://foo.bar:44/path"
    sub_condition.condition = generate_class_instance(Sep2Condition)
    sub_condition.condition.attributeIdentifier = ConditionAttributeIdentifier.READING_VALUE

    scope_prefix: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, site_id=None, href_prefix="/prefix"
    )
    valid_domains = set(["foo.bar", "example.com"])
    changed_time = datetime(2022, 3, 4, 5, 6, 7)

    result_all_set = SubscriptionMapper.map_from_request(sub_all_set, scope_prefix, valid_domains, changed_time)
    assert isinstance(result_all_set, Subscription)
    assert not result_all_set.subscription_id
    assert result_all_set.resource_type == SubscriptionResource.SITE
    assert result_all_set.scoped_site_id == 123
    assert result_all_set.resource_id is None
    assert not result_all_set.conditions

    result_optional = SubscriptionMapper.map_from_request(sub_optional, scope_prefix, valid_domains, changed_time)
    assert isinstance(result_optional, Subscription)
    assert not result_optional.subscription_id
    assert result_optional.resource_type == SubscriptionResource.SITE
    assert result_optional.scoped_site_id == 123
    assert result_optional.resource_id is None
    assert not result_optional.conditions

    result_condition = SubscriptionMapper.map_from_request(sub_condition, scope_prefix, valid_domains, changed_time)
    assert isinstance(result_condition, Subscription)
    assert not result_condition.subscription_id
    assert result_condition.resource_type == SubscriptionResource.SITE
    assert result_condition.scoped_site_id == 123
    assert result_condition.resource_id is None
    assert len(result_condition.conditions) == 1


@pytest.mark.parametrize(
    "href, expected",
    [
        ("/edev", (SubscriptionResource.SITE, None, None)),
        ("/edev/123", (SubscriptionResource.SITE, 123, None)),
        (f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}", (SubscriptionResource.SITE, None, None)),
        ("/edev/123-a", InvalidMappingError),
        ("/edev/", InvalidMappingError),
        ("/upt/11/mr/22/rs/all/r", (SubscriptionResource.READING, 11, 22)),
        (f"/upt/{VIRTUAL_END_DEVICE_SITE_ID}/mr/22/rs/all/r", (SubscriptionResource.READING, None, 22)),
        ("/upt/11/mr/22/rs/all/", InvalidMappingError),
        ("/upt/11/mr/22/rs/allbutnot/r", InvalidMappingError),
        ("/upt/11/mr/22-2/rs/all/r", InvalidMappingError),
        ("/upt/11-2/mr/22/rs/all/r", InvalidMappingError),
        ("/edev/33/tp/44/rc", (SubscriptionResource.TARIFF_GENERATED_RATE, 33, 44)),
        (f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}/tp/44/rc", (SubscriptionResource.TARIFF_GENERATED_RATE, None, 44)),
        ("/edev/33nan/tp/44/rc", InvalidMappingError),
        ("/edev/33/tp/44-4/rc", InvalidMappingError),
        ("/edev/55/derp/doe/derc", (SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, 55, None)),
        (
            f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}/derp/doe/derc",
            (SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, None, None),
        ),
        ("/edev/55/derp/doe_but_not/derc", InvalidMappingError),
        ("/edev/55-3/derp/doe/derc", InvalidMappingError),
        ("/edev/55/derp/doe", InvalidMappingError),
        ("/edev/55/der/1/dera", (SubscriptionResource.SITE_DER_AVAILABILITY, 55, 1)),
        (f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}/der/1/dera", (SubscriptionResource.SITE_DER_AVAILABILITY, None, 1)),
        ("/edev/55/der/1/dera/other", InvalidMappingError),
        ("/edev/55/der/1/derg", (SubscriptionResource.SITE_DER_SETTING, 55, 1)),
        (f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}/der/1/derg", (SubscriptionResource.SITE_DER_SETTING, None, 1)),
        ("/edev/55/der/1/dercap", (SubscriptionResource.SITE_DER_RATING, 55, 1)),
        (f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}/der/1/dercap", (SubscriptionResource.SITE_DER_RATING, None, 1)),
        ("/edev/55/der/1/ders", (SubscriptionResource.SITE_DER_STATUS, 55, 1)),
        (f"/edev/{VIRTUAL_END_DEVICE_SITE_ID}/der/1/ders", (SubscriptionResource.SITE_DER_STATUS, None, 1)),
        ("/edev/55/der/1/derx", InvalidMappingError),
        ("/", InvalidMappingError),
        ("edev", InvalidMappingError),
        ("edev/123", InvalidMappingError),
        ("/edev/123/subbutnotreally/1", InvalidMappingError),
    ],
)
def test_SubscriptionMapper_parse_resource_href(href: str, expected: Union[tuple, Exception]):
    if isinstance(expected, tuple):
        assert SubscriptionMapper.parse_resource_href(href) == expected
    else:
        with pytest.raises(expected):
            SubscriptionMapper.parse_resource_href(href)


def test_NotificationMapper_map_sites_to_response():
    site1: Site = generate_class_instance(Site, seed=101, optional_is_none=False)
    site2: Site = generate_class_instance(Site, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/custom/prefix"
    )

    notification = NotificationMapper.map_sites_to_response([site1, site2], sub, scope)
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert EndDeviceListUri in notification.subscribedResource
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_END_DEVICE_LIST
    assert_list_type(EndDeviceResponse, notification.resource.EndDevice, count=2)
    assert_entity_hrefs_contain_entity_id_and_prefix(
        [e.href for e in notification.resource.EndDevice], [site1.site_id, site2.site_id], scope.href_prefix
    )


def test_NotificationMapper_map_does_to_response():
    doe1: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False)
    doe2: DynamicOperatingEnvelope = generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/custom/prefix"
    )

    notification = NotificationMapper.map_does_to_response([doe1, doe2], sub, scope)
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert (
        DERControlListUri.format(site_id=scope.display_site_id, der_program_id=DOE_PROGRAM_ID)
        in notification.subscribedResource
    )
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_DER_CONTROL_LIST
    assert_list_type(DERControlResponse, notification.resource.DERControl, count=2)
    assert_entity_hrefs_contain_entity_id_and_prefix(
        [e.href for e in notification.resource.DERControl],
        [doe1.dynamic_operating_envelope_id, doe2.dynamic_operating_envelope_id],
        scope.href_prefix,
    )


def test_NotificationMapper_map_readings_to_response():
    sr1: SiteReading = generate_class_instance(SiteReading, seed=101, optional_is_none=False)
    sr2: SiteReading = generate_class_instance(SiteReading, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/custom/prefix"
    )
    site_reading_type_id = 456

    notification = NotificationMapper.map_readings_to_response(site_reading_type_id, [sr1, sr2], sub, scope)
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert "/upt/" in notification.subscribedResource, "A UsagePoint URI should be utilised"
    assert f"/{scope.display_site_id}" in notification.subscribedResource
    assert f"/{site_reading_type_id}" in notification.subscribedResource
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_READING_LIST
    assert_list_type(Reading, notification.resource.Readings, count=2)
    assert all(
        [e.href is None for e in notification.resource.Readings]
    ), "If this fails - starting testing using assert_entity_hrefs_contain_entity_id_and_prefix (see other tests)"


def test_NotificationMapper_map_rates_to_response():
    rate1: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False)
    rate2: TariffGeneratedRate = generate_class_instance(TariffGeneratedRate, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    scope: DeviceOrAggregatorRequestScope = generate_class_instance(
        DeviceOrAggregatorRequestScope, seed=1001, href_prefix="/custom/prefix"
    )
    tariff_id = 888
    day = datetime.now().date()
    pricing_reading_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH

    notification = NotificationMapper.map_rates_to_response(
        tariff_id, day, pricing_reading_type, [rate1, rate2], sub, scope
    )
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert str(int(pricing_reading_type)) in notification.subscribedResource
    assert str(scope.display_site_id) in notification.subscribedResource
    assert str(tariff_id) in notification.subscribedResource
    assert "/tti" in notification.subscribedResource, "This should be a time tariff interval list href"
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_TIME_TARIFF_INTERVAL_LIST
    assert_list_type(TimeTariffIntervalResponse, notification.resource.TimeTariffInterval, count=2)
    assert_entity_hrefs_contain_entity_id_and_prefix(
        [e.href for e in notification.resource.TimeTariffInterval], [rate1.site_id, rate2.site_id], scope.href_prefix
    )


def test_NotificationMapper_map_der_availability_to_response_missing():

    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, href_prefix="/custom/prefix")
    der_id = 456

    notification_all_set = NotificationMapper.map_der_availability_to_response(der_id, None, 99, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert (
        DERAvailabilityUri.format(site_id=scope.display_site_id, der_id=der_id)
        in notification_all_set.subscribedResource
    )
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI

    assert notification_all_set.resource is None


def test_NotificationMapper_map_der_availability_to_response():
    all_set: SiteDERAvailability = generate_class_instance(SiteDERAvailability, seed=1, optional_is_none=False)

    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, href_prefix="/custom/prefix")
    der_id = 456
    site_id = 789

    notification_all_set = NotificationMapper.map_der_availability_to_response(der_id, all_set, site_id, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert (
        DERAvailabilityUri.format(site_id=scope.display_site_id, der_id=der_id)
        in notification_all_set.subscribedResource
    )
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI
    assert f"/{scope.display_site_id}" in notification_all_set.subscribedResource, "Subscription uses display site ID"
    assert f"/{site_id}" in notification_all_set.resource.href, "Resource uses the actual site id"

    # Sanity check to ensure we have some of the right fields set - the heavy lifting is done on the entity
    # mapper unit tests
    assert notification_all_set.resource.type == XSI_TYPE_DER_AVAILABILITY
    assert notification_all_set.resource.statWAvail.value == all_set.estimated_w_avail_value
    assert notification_all_set.resource.statWAvail.multiplier == all_set.estimated_w_avail_multiplier
    assert notification_all_set.resource.reservePercent == int(all_set.reserved_deliver_percent * 100)


def test_NotificationMapper_map_der_rating_to_response_missing():
    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, href_prefix="/custom/prefix")
    der_id = 456

    notification_all_set = NotificationMapper.map_der_rating_to_response(der_id, None, 999, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert (
        DERCapabilityUri.format(site_id=scope.display_site_id, der_id=der_id) in notification_all_set.subscribedResource
    )
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI

    assert notification_all_set.resource is None


def test_NotificationMapper_map_der_rating_to_response():
    all_set: SiteDERRating = generate_class_instance(SiteDERRating, seed=1, optional_is_none=False)

    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, href_prefix="/custom/prefix")
    der_id = 456
    site_id = 789

    notification_all_set = NotificationMapper.map_der_rating_to_response(der_id, all_set, site_id, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert (
        DERCapabilityUri.format(site_id=scope.display_site_id, der_id=der_id) in notification_all_set.subscribedResource
    )
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI
    assert f"/{scope.display_site_id}" in notification_all_set.subscribedResource, "Subscription uses display site ID"
    assert f"/{site_id}" in notification_all_set.resource.href, "Resource uses the actual site id"

    # Sanity check to ensure we have some of the right fields set - the heavy lifting is done on the entity
    # mapper unit tests
    assert notification_all_set.resource.type == XSI_TYPE_DER_CAPABILITY
    assert notification_all_set.resource.rtgMaxW.value == all_set.max_w_value
    assert notification_all_set.resource.rtgMaxW.multiplier == all_set.max_w_multiplier
    assert notification_all_set.resource.rtgMaxV.value == all_set.max_v_value


def test_NotificationMapper_map_der_settings_to_response_missing():
    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, href_prefix="/custom/prefix")
    der_id = 456

    notification_all_set = NotificationMapper.map_der_settings_to_response(der_id, None, 999, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert (
        DERSettingsUri.format(site_id=scope.display_site_id, der_id=der_id) in notification_all_set.subscribedResource
    )
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI

    assert notification_all_set.resource is None


def test_NotificationMapper_map_der_settings_to_response():
    all_set: SiteDERSetting = generate_class_instance(SiteDERSetting, seed=1, optional_is_none=False)

    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, href_prefix="/custom/prefix")
    der_id = 456
    site_id = 789

    notification_all_set = NotificationMapper.map_der_settings_to_response(der_id, all_set, site_id, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert (
        DERSettingsUri.format(site_id=scope.display_site_id, der_id=der_id) in notification_all_set.subscribedResource
    )
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI
    assert f"/{scope.display_site_id}" in notification_all_set.subscribedResource, "Subscription uses display site ID"
    assert f"/{site_id}" in notification_all_set.resource.href, "Resource uses the actual site id"

    # Sanity check to ensure we have some of the right fields set - the heavy lifting is done on the entity
    # mapper unit tests
    assert notification_all_set.resource.type == XSI_TYPE_DER_SETTINGS
    assert notification_all_set.resource.setMaxW.value == all_set.max_w_value
    assert notification_all_set.resource.setMaxW.multiplier == all_set.max_w_multiplier
    assert notification_all_set.resource.setMaxV.value == all_set.max_v_value
    assert notification_all_set.resource.setESDelay == all_set.es_delay


def test_NotificationMapper_map_der_status_to_response_missing():
    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, href_prefix="/custom/prefix")
    der_id = 456

    notification_all_set = NotificationMapper.map_der_status_to_response(der_id, None, 998, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert DERStatusUri.format(site_id=scope.display_site_id, der_id=der_id) in notification_all_set.subscribedResource
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI
    assert notification_all_set.resource is None


def test_NotificationMapper_map_der_status_to_response():
    all_set: SiteDERStatus = generate_class_instance(SiteDERStatus, seed=1, optional_is_none=False)

    sub = generate_class_instance(Subscription, seed=303)
    scope: SiteRequestScope = generate_class_instance(SiteRequestScope, seed=1001, href_prefix="/custom/prefix")
    der_id = 456
    site_id = 789

    notification_all_set = NotificationMapper.map_der_status_to_response(der_id, all_set, site_id, sub, scope)
    assert isinstance(notification_all_set, Notification)
    assert notification_all_set.subscribedResource.startswith("/custom/prefix")
    assert DERStatusUri.format(site_id=scope.display_site_id, der_id=der_id) in notification_all_set.subscribedResource
    assert notification_all_set.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification_all_set.subscriptionURI
    assert f"/{scope.display_site_id}" in notification_all_set.subscribedResource, "Subscription uses display site ID"
    assert f"/{site_id}" in notification_all_set.resource.href, "Resource uses the actual site id"

    # Sanity check to ensure we have some of the right fields set - the heavy lifting is done on the entity
    # mapper unit tests
    assert notification_all_set.resource.type == XSI_TYPE_DER_STATUS
    assert notification_all_set.resource.inverterStatus.value == all_set.inverter_status
    assert notification_all_set.resource.inverterStatus.dateTime == int(all_set.inverter_status_time.timestamp())
    assert notification_all_set.resource.operationalModeStatus.value == all_set.operational_mode_status
    assert notification_all_set.resource.genConnectStatus.value == to_hex_binary(all_set.generator_connect_status)
