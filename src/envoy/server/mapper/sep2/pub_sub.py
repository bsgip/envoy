from datetime import date
from typing import Sequence

from envoy_schema.server.schema.sep2.pub_sub import (
    XSI_TYPE_DER_CONTROL_LIST,
    XSI_TYPE_END_DEVICE_LIST,
    XSI_TYPE_READING_LIST,
    XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
    Notification,
    NotificationStatus,
)
from envoy_schema.server.schema.uri import (
    DERControlListUri,
    EndDeviceListUri,
    ReadingListUri,
    SubscriptionGlobalUri,
    SubscriptionUri,
    TimeTariffIntervalListUri,
)

from envoy.server.mapper.common import generate_href
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID, DERControlMapper
from envoy.server.mapper.sep2.end_device import EndDeviceMapper
from envoy.server.mapper.sep2.metering import READING_SET_ALL_ID, MirrorMeterReadingMapper
from envoy.server.mapper.sep2.pricing import PricingReadingType, TimeTariffIntervalMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_state import RequestStateParameters


class NotificationMapper:
    @staticmethod
    def calculate_subscription_href(sub: Subscription, rs_params: RequestStateParameters) -> str:
        """Calculates the href for a subscription - this will vary depending on whether the subscription
        is narrowed to a particular end_device or is unscoped"""
        if sub.scoped_site_id is None:
            return generate_href(SubscriptionGlobalUri, rs_params, subscription_id=sub.subscription_id)
        else:
            return generate_href(
                SubscriptionUri, rs_params, site_id=sub.scoped_site_id, subscription_id=sub.subscription_id
            )

    @staticmethod
    def map_sites_to_response(
        sites: Sequence[Site], sub: Subscription, rs_params: RequestStateParameters
    ) -> Notification:
        """Turns a list of sites into a notification"""
        return Notification.model_validate(
            {
                "subscribedResource": generate_href(EndDeviceListUri, rs_params),
                "subscriptionURI": NotificationMapper.calculate_subscription_href(sub, rs_params),
                "status": NotificationStatus.DEFAULT,
                "resource": {
                    "type": XSI_TYPE_END_DEVICE_LIST,
                    "all_": len(sites),
                    "results": len(sites),
                    "EndDevice": [EndDeviceMapper.map_to_response(rs_params, s) for s in sites],
                },
            }
        )

    @staticmethod
    def map_does_to_response(
        site_id: int, does: Sequence[DynamicOperatingEnvelope], sub: Subscription, rs_params: RequestStateParameters
    ) -> Notification:
        """Turns a list of does into a notification"""
        # DERControlListUri = "/edev/{site_id}/derp/{der_program_id}/derc"
        doe_list_href = generate_href(DERControlListUri, rs_params, site_id=site_id, der_program_id=DOE_PROGRAM_ID)
        return Notification.model_validate(
            {
                "subscribedResource": doe_list_href,
                "subscriptionURI": NotificationMapper.calculate_subscription_href(sub, rs_params),
                "status": NotificationStatus.DEFAULT,
                "resource": {
                    "type": XSI_TYPE_DER_CONTROL_LIST,
                    "all_": len(does),
                    "results": len(does),
                    "DERControl": [DERControlMapper.map_to_response(d) for d in does],
                },
            }
        )

    @staticmethod
    def map_readings_to_response(
        site_id: int,
        site_reading_type_id: int,
        readings: Sequence[SiteReading],
        sub: Subscription,
        rs_params: RequestStateParameters,
    ) -> Notification:
        """Turns a list of does into a notification"""
        reading_list_href = generate_href(
            ReadingListUri,
            rs_params,
            site_id=site_id,
            site_reading_type_id=site_reading_type_id,
            reading_set_id=READING_SET_ALL_ID,  # Can't correlate this back to anything else - all will be fine
        )
        return Notification.model_validate(
            {
                "subscribedResource": reading_list_href,
                "subscriptionURI": NotificationMapper.calculate_subscription_href(sub, rs_params),
                "status": NotificationStatus.DEFAULT,
                "resource": {
                    "type": XSI_TYPE_READING_LIST,
                    "all_": len(readings),
                    "results": len(readings),
                    "Readings": [MirrorMeterReadingMapper.map_to_response(r) for r in readings],
                },
            }
        )

    @staticmethod
    def map_rates_to_response(
        site_id: int,
        tariff_id: int,
        day: date,
        pricing_reading_type: PricingReadingType,
        rates: Sequence[TariffGeneratedRate],
        sub: Subscription,
        rs_params: RequestStateParameters,
    ) -> Notification:
        """Turns a list of dynamic prices into a notification"""
        time_tariff_interval_list_href = generate_href(
            TimeTariffIntervalListUri,
            rs_params,
            site_id=site_id,
            tariff_id=tariff_id,
            rate_component_id=day.isoformat(),
            pricing_reading=int(pricing_reading_type),
        )
        return Notification.model_validate(
            {
                "subscribedResource": time_tariff_interval_list_href,
                "subscriptionURI": NotificationMapper.calculate_subscription_href(sub, rs_params),
                "status": NotificationStatus.DEFAULT,
                "resource": {
                    "type": XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
                    "all_": len(rates),
                    "results": len(rates),
                    "TimeTariffInterval": [
                        TimeTariffIntervalMapper.map_to_response(rs_params, r, pricing_reading_type) for r in rates
                    ],
                },
            }
        )
