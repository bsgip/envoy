from datetime import datetime

from envoy_schema.server.schema.sep2.der import DERControlResponse
from envoy_schema.server.schema.sep2.end_device import EndDeviceResponse
from envoy_schema.server.schema.sep2.metering import Reading
from envoy_schema.server.schema.sep2.pricing import TimeTariffIntervalResponse
from envoy_schema.server.schema.sep2.pub_sub import (
    XSI_TYPE_DER_CONTROL_LIST,
    XSI_TYPE_END_DEVICE_LIST,
    XSI_TYPE_READING_LIST,
    XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
    Notification,
)
from envoy_schema.server.schema.uri import DERControlListUri, EndDeviceListUri

from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.mapper.sep2.pub_sub import NotificationMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_state import RequestStateParameters
from tests.data.fake.generator import generate_class_instance


def test_NotificationMapper_calculate_subscription_href():
    """Validates that the hrefs don't raise errors and vary depending on inputs"""
    # Using the same keys -
    sub_all_set = generate_class_instance(Subscription, seed=101, optional_is_none=False)
    sub_optional = generate_class_instance(Subscription, seed=101, optional_is_none=True)

    rs_params_base = RequestStateParameters(aggregator_id=1, href_prefix=None)
    rs_params_prefix = RequestStateParameters(aggregator_id=1, href_prefix="/my/prefix")

    # Subscriptions scoped to a EndDevice are different to those that are "global"
    assert NotificationMapper.calculate_subscription_href(
        sub_all_set, rs_params_base
    ) != NotificationMapper.calculate_subscription_href(sub_optional, rs_params_base)
    assert NotificationMapper.calculate_subscription_href(
        sub_all_set, rs_params_prefix
    ) != NotificationMapper.calculate_subscription_href(sub_optional, rs_params_prefix)

    # The href_prefix is included
    assert NotificationMapper.calculate_subscription_href(
        sub_all_set, rs_params_base
    ) != NotificationMapper.calculate_subscription_href(sub_all_set, rs_params_prefix)
    assert NotificationMapper.calculate_subscription_href(
        sub_optional, rs_params_base
    ) != NotificationMapper.calculate_subscription_href(sub_optional, rs_params_prefix)


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
