from datetime import datetime
from itertools import product
from typing import Optional, Union, cast

import pytest
from envoy_schema.server.schema.sep2.der import DERControlResponse
from envoy_schema.server.schema.sep2.end_device import EndDeviceResponse
from envoy_schema.server.schema.sep2.metering import Reading
from envoy_schema.server.schema.sep2.pricing import TimeTariffIntervalResponse
from envoy_schema.server.schema.sep2.pub_sub import (
    XSI_TYPE_DER_CONTROL_LIST,
    XSI_TYPE_END_DEVICE_LIST,
    XSI_TYPE_READING_LIST,
    XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
)
from envoy_schema.server.schema.sep2.pub_sub import Condition as Sep2Condition
from envoy_schema.server.schema.sep2.pub_sub import ConditionAttributeIdentifier, Notification
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionListResponse
from envoy_schema.server.schema.uri import DERControlListUri, EndDeviceListUri

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.mapper.sep2.pub_sub import NotificationMapper, SubscriptionListMapper, SubscriptionMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_state import RequestStateParameters
from tests.data.fake.generator import generate_class_instance


@pytest.mark.parametrize("resource, site_id, resource_id", product(SubscriptionResource, [1, None], [2, None]))
def test_SubscriptionMapper_calculate_resource_href_uses_prefix(
    resource: SubscriptionResource, site_id: Optional[int], resource_id: Optional[int]
):
    """Validates the various inputs/expected outputs apply the href_prefix"""
    sub: Subscription = generate_class_instance(Subscription)
    sub.resource_type = resource
    sub.scoped_site_id = site_id
    sub.resource_id = resource_id

    # set output to None if we hit an unsupported combo of inputs
    href_no_prefix: Optional[str]
    try:
        href_no_prefix = SubscriptionMapper.calculate_resource_href(sub, RequestStateParameters(99, None))
        assert href_no_prefix
    except InvalidMappingError:
        href_no_prefix = None

    # set output to None if we hit an unsupported combo of inputs
    prefix = "/my/prefix/for/tests"
    href_with_prefix: Optional[str]
    try:
        href_with_prefix = SubscriptionMapper.calculate_resource_href(sub, RequestStateParameters(99, prefix))
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
        assert href_with_prefix == generate_href(href_no_prefix, RequestStateParameters(99, prefix))


def test_SubscriptionMapper_calculate_resource_href_bad_type():
    sub: Subscription = generate_class_instance(Subscription)
    sub.resource_type = 9876  # invalid type
    with pytest.raises(InvalidMappingError):
        SubscriptionMapper.calculate_resource_href(sub, RequestStateParameters(99, None))


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
        sub.resource_type = resource
        sub.scoped_site_id = site_id
        sub.resource_id = resource_id

        try:
            href = SubscriptionMapper.calculate_resource_href(sub, RequestStateParameters(99, None))
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
    assert total_fails < 10, "There shouldn't be this many combinations generating InvalidMappingError - go investigate"


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

    rs_params_base = RequestStateParameters(aggregator_id=1, href_prefix=None)
    rs_params_prefix = RequestStateParameters(aggregator_id=1, href_prefix="/my/prefix")

    # check prefix is applied
    sep2_prefix = SubscriptionMapper.map_to_response(sub_all_set, rs_params_prefix)
    assert sep2_prefix.href and isinstance(sep2_prefix.href, str)
    assert sep2_prefix.href.startswith(rs_params_prefix.href_prefix)
    assert sep2_prefix.subscribedResource and isinstance(sep2_prefix.subscribedResource, str)
    assert sep2_prefix.subscribedResource.startswith(rs_params_prefix.href_prefix)
    assert rs_params_prefix.href_prefix not in sep2_prefix.notificationURI

    # Check a boring sub
    sep2_all_set = SubscriptionMapper.map_to_response(sub_all_set, rs_params_base)
    assert isinstance(sep2_all_set, Sep2Subscription)
    assert sep2_all_set.condition is None
    assert sep2_all_set.href and isinstance(sep2_all_set.href, str)
    assert sep2_all_set.subscribedResource and isinstance(sep2_all_set.subscribedResource, str)
    assert sep2_all_set.notificationURI == sub_all_set.notification_uri
    assert sep2_all_set.limit == sub_all_set.entity_limit

    sep2_optional = SubscriptionMapper.map_to_response(sub_optional, rs_params_base)
    assert isinstance(sep2_optional, Sep2Subscription)
    assert sep2_optional.condition is None
    assert sep2_optional.href and isinstance(sep2_optional.href, str)
    assert sep2_optional.subscribedResource and isinstance(sep2_optional.subscribedResource, str)
    assert sep2_optional.notificationURI == sub_optional.notification_uri
    assert sep2_optional.limit == sub_optional.entity_limit

    sep2_condition = SubscriptionMapper.map_to_response(sub_with_condition, rs_params_base)
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
    site_id = 876
    rs_params = RequestStateParameters(1, "/custom/prefix")

    mapped = SubscriptionListMapper.map_to_site_response(rs_params, site_id, sub_list, sub_count)

    assert isinstance(mapped, SubscriptionListResponse)
    assert str(site_id) in mapped.href
    assert mapped.results == len(sub_list)
    assert mapped.all_ == sub_count
    assert len(mapped.subscriptions) == len(sub_list)
    assert all([isinstance(s, Sep2Subscription) for s in mapped.subscriptions])


def test_SubscriptionMapper_calculate_subscription_href():
    """Validates that the hrefs don't raise errors and vary depending on inputs"""
    # Using the same keys -
    sub_all_set = generate_class_instance(Subscription, seed=101, optional_is_none=False)
    sub_optional = generate_class_instance(Subscription, seed=101, optional_is_none=True)

    rs_params_base = RequestStateParameters(aggregator_id=1, href_prefix=None)
    rs_params_prefix = RequestStateParameters(aggregator_id=1, href_prefix="/my/prefix")

    # Subscriptions scoped to a EndDevice are different to those that are "global"
    assert SubscriptionMapper.calculate_subscription_href(
        sub_all_set, rs_params_base
    ) != SubscriptionMapper.calculate_subscription_href(sub_optional, rs_params_base)
    assert SubscriptionMapper.calculate_subscription_href(
        sub_all_set, rs_params_prefix
    ) != SubscriptionMapper.calculate_subscription_href(sub_optional, rs_params_prefix)

    # The href_prefix is included
    assert SubscriptionMapper.calculate_subscription_href(
        sub_all_set, rs_params_base
    ) != SubscriptionMapper.calculate_subscription_href(sub_all_set, rs_params_prefix)
    assert SubscriptionMapper.calculate_subscription_href(
        sub_optional, rs_params_base
    ) != SubscriptionMapper.calculate_subscription_href(sub_optional, rs_params_prefix)


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

    rs_params_prefix = RequestStateParameters(aggregator_id=1, href_prefix="/prefix")
    valid_domains = set(["foo.bar", "example.com"])
    changed_time = datetime(2022, 3, 4, 5, 6, 7)

    result_all_set = SubscriptionMapper.map_from_request(sub_all_set, rs_params_prefix, valid_domains, changed_time)
    assert isinstance(result_all_set, Subscription)
    assert not result_all_set.subscription_id
    assert result_all_set.resource_type == SubscriptionResource.SITE
    assert result_all_set.scoped_site_id == 123
    assert result_all_set.resource_id is None
    assert not result_all_set.conditions

    result_optional = SubscriptionMapper.map_from_request(sub_optional, rs_params_prefix, valid_domains, changed_time)
    assert isinstance(result_optional, Subscription)
    assert not result_optional.subscription_id
    assert result_optional.resource_type == SubscriptionResource.SITE
    assert result_optional.scoped_site_id == 123
    assert result_optional.resource_id is None
    assert not result_optional.conditions

    result_condition = SubscriptionMapper.map_from_request(sub_condition, rs_params_prefix, valid_domains, changed_time)
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
        ("/edev/123-a", InvalidMappingError),
        ("/edev/", InvalidMappingError),
        ("/upt/11/mr/22/rs/all/r", (SubscriptionResource.READING, 11, 22)),
        ("/upt/11/mr/22/rs/all/", InvalidMappingError),
        ("/upt/11/mr/22/rs/allbutnot/r", InvalidMappingError),
        ("/upt/11/mr/22-2/rs/all/r", InvalidMappingError),
        ("/upt/11-2/mr/22/rs/all/r", InvalidMappingError),
        ("/edev/33/tp/44/rc", (SubscriptionResource.TARIFF_GENERATED_RATE, 33, 44)),
        ("/edev/33nan/tp/44/rc", InvalidMappingError),
        ("/edev/33/tp/44-4/rc", InvalidMappingError),
        ("/edev/55/derp/doe/derc", (SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, 55, None)),
        ("/edev/55/derp/doe_but_not/derc", InvalidMappingError),
        ("/edev/55-3/derp/doe/derc", InvalidMappingError),
        ("/edev/55/derp/doe", InvalidMappingError),
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
    site1 = generate_class_instance(Site, seed=101, optional_is_none=False)
    site2 = generate_class_instance(Site, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    rs_params = RequestStateParameters(1, "/custom/prefix")

    notification = NotificationMapper.map_sites_to_response([site1, site2], sub, rs_params)
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert EndDeviceListUri in notification.subscribedResource
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_END_DEVICE_LIST
    assert len(notification.resource.EndDevice) == 2
    assert all([isinstance(r, EndDeviceResponse) for r in notification.resource.EndDevice])


def test_NotificationMapper_map_does_to_response():
    doe1 = generate_class_instance(DynamicOperatingEnvelope, seed=101, optional_is_none=False)
    doe2 = generate_class_instance(DynamicOperatingEnvelope, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    rs_params = RequestStateParameters(1, "/custom/prefix")
    site_id = 123

    notification = NotificationMapper.map_does_to_response(site_id, [doe1, doe2], sub, rs_params)
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert DERControlListUri.format(site_id=site_id, der_program_id=DOE_PROGRAM_ID) in notification.subscribedResource
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_DER_CONTROL_LIST
    assert len(notification.resource.DERControl) == 2
    assert all([isinstance(r, DERControlResponse) for r in notification.resource.DERControl])


def test_NotificationMapper_map_readings_to_response():
    sr1 = generate_class_instance(SiteReading, seed=101, optional_is_none=False)
    sr2 = generate_class_instance(SiteReading, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    rs_params = RequestStateParameters(1, "/custom/prefix")
    site_id = 123
    site_reading_type_id = 456

    notification = NotificationMapper.map_readings_to_response(
        site_id, site_reading_type_id, [sr1, sr2], sub, rs_params
    )
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert "/upt/" in notification.subscribedResource, "A UsagePoint URI should be utilised"
    assert str(site_id) in notification.subscribedResource
    assert str(site_reading_type_id) in notification.subscribedResource
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_READING_LIST
    assert len(notification.resource.Readings) == 2
    assert all([isinstance(r, Reading) for r in notification.resource.Readings])


def test_NotificationMapper_map_rates_to_response():
    rate1 = generate_class_instance(TariffGeneratedRate, seed=101, optional_is_none=False)
    rate2 = generate_class_instance(TariffGeneratedRate, seed=202, optional_is_none=True)

    sub = generate_class_instance(Subscription, seed=303)
    rs_params = RequestStateParameters(1, "/custom/prefix")
    site_id = 999
    tariff_id = 888
    day = datetime.now().date()
    pricing_reading_type = PricingReadingType.IMPORT_ACTIVE_POWER_KWH

    notification = NotificationMapper.map_rates_to_response(
        site_id, tariff_id, day, pricing_reading_type, [rate1, rate2], sub, rs_params
    )
    assert isinstance(notification, Notification)
    assert notification.subscribedResource.startswith("/custom/prefix")
    assert str(int(pricing_reading_type)) in notification.subscribedResource
    assert str(site_id) in notification.subscribedResource
    assert str(tariff_id) in notification.subscribedResource
    assert "/tti" in notification.subscribedResource, "This should be a time tariff interval list href"
    assert notification.subscriptionURI.startswith("/custom/prefix")
    assert "/sub" in notification.subscriptionURI

    assert notification.resource.type == XSI_TYPE_TIME_TARIFF_INTERVAL_LIST
    assert len(notification.resource.TimeTariffInterval) == 2
    assert all([isinstance(r, TimeTariffIntervalResponse) for r in notification.resource.TimeTariffInterval])
