from datetime import date, datetime
from typing import Optional, Sequence
from urllib.parse import urlparse

from envoy_schema.server.schema.sep2.pub_sub import (
    XSI_TYPE_DER_CONTROL_LIST,
    XSI_TYPE_END_DEVICE_LIST,
    XSI_TYPE_READING_LIST,
    XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
)
from envoy_schema.server.schema.sep2.pub_sub import Condition as Sep2Condition
from envoy_schema.server.schema.sep2.pub_sub import Notification, NotificationStatus
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionEncoding, SubscriptionListResponse
from envoy_schema.server.schema.uri import (
    DERControlListUri,
    EndDeviceListUri,
    EndDeviceUri,
    RateComponentListUri,
    ReadingListUri,
    SubscriptionGlobalUri,
    SubscriptionListUri,
    SubscriptionUri,
    TimeTariffIntervalListUri,
)
from parse import parse  # type: ignore

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href, remove_href_prefix
from envoy.server.mapper.csip_aus.doe import DOE_PROGRAM_ID, DERControlMapper
from envoy.server.mapper.sep2.end_device import EndDeviceMapper
from envoy.server.mapper.sep2.metering import READING_SET_ALL_ID, MirrorMeterReadingMapper
from envoy.server.mapper.sep2.pricing import PricingReadingType, TimeTariffIntervalMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.site import Site
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_state import RequestStateParameters


class SubscriptionMapper:
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
    def calculate_resource_href(sub: Subscription, rs_params: RequestStateParameters) -> str:
        """Calculates the href for a Subscription.subscribedResource based on what the subscription is tracking

        Some combos of resource_type/scoped_site_id/resource_id may be invalid and will raise InvalidMappingError"""
        if sub.resource_type == SubscriptionResource.SITE:
            if sub.scoped_site_id is None:
                return generate_href(EndDeviceListUri, rs_params)
            else:
                return generate_href(EndDeviceUri, rs_params, site_id=sub.scoped_site_id)
        elif sub.resource_type == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
            if sub.scoped_site_id is None:
                raise InvalidMappingError(
                    f"Subscribing to DOEs without a scoped_site_id is unsupported on sub {sub.subscription_id}"
                )

            if sub.resource_id is not None:
                raise InvalidMappingError(
                    f"Subscribing to DOEs with resource_id is unsupported on sub {sub.subscription_id}"
                )

            return generate_href(
                DERControlListUri, rs_params, site_id=sub.scoped_site_id, der_program_id=DOE_PROGRAM_ID
            )
        elif sub.resource_type == SubscriptionResource.READING:
            if sub.scoped_site_id is None:
                raise InvalidMappingError(
                    f"Subscribing to readings without a scoped_site_id is unsupported on sub {sub.subscription_id}"
                )

            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to readings without a resource_id is unsupported on sub {sub.subscription_id}"
                )

            return generate_href(
                ReadingListUri,
                rs_params,
                site_id=sub.scoped_site_id,
                site_reading_type_id=sub.resource_id,
                reading_set_id=READING_SET_ALL_ID,
            )
        elif sub.resource_type == SubscriptionResource.TARIFF_GENERATED_RATE:
            if sub.scoped_site_id is None:
                raise InvalidMappingError(
                    f"Subscribing to rates without a scoped_site_id is unsupported on sub {sub.subscription_id}"
                )

            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to rates without a resource_id is unsupported on sub {sub.subscription_id}"
                )

            # We have to make a fun decision here - given our subs don't technically support subscribing
            # at a TimeTariffInterval level (which would actually be subscribing to a single day's prices)
            # we can either:
            #   a) Subscribe to the parent RateComponent which is scoped to site/tariff (and then return
            #      TimeTariffInterval for ALL price types in notifications)
            #   b) Subscribe to the TimeTariffInterval but instead return ALL dates/price types despite
            #      the subscribedResourceUri
            #
            # Both are annoying - I think option a) feels the least hacky (as both break the standard slightly
            # in different ways)
            return generate_href(
                RateComponentListUri,
                rs_params,
                site_id=sub.scoped_site_id,
                tariff_id=sub.resource_id,
            )
        else:
            raise InvalidMappingError(
                f"Cannot map a resource HREF for resource_type {sub.resource_type} on sub {sub.subscription_id}"
            )

    @staticmethod
    def map_to_response_condition(condition: SubscriptionCondition) -> Sep2Condition:
        return Sep2Condition.model_validate(
            {
                "attributeIdentifier": condition.attribute,
                "lowerThreshold": condition.lower_threshold,
                "upperThreshold": condition.upper_threshold,
            }
        )

    @staticmethod
    def map_to_response(sub: Subscription, rs_params: RequestStateParameters) -> Sep2Subscription:
        """Maps an internal Subscription model to the Sep2 model Equivalent"""
        condition: Optional[Sep2Condition] = None
        if sub.conditions and len(sub.conditions) > 0:
            condition = SubscriptionMapper.map_to_response_condition(sub.conditions[0])

        return Sep2Subscription.model_validate(
            {
                "href": SubscriptionMapper.calculate_subscription_href(sub, rs_params),
                "encoding": SubscriptionEncoding.XML,
                "level": "+S1",
                "limit": sub.entity_limit,
                "notificationURI": sub.notification_uri,
                "subscribedResource": SubscriptionMapper.calculate_resource_href(sub, rs_params),
                "condition": condition,
            }
        )

    @staticmethod
    def parse_resource_href(href: str) -> tuple[SubscriptionResource, Optional[int], Optional[int]]:
        """Takes a subscription subscribed resource href (sans any href_prefix) and attempts to decompose it into
        (resource, scoped_site_id, resource_id) - raises InvalidMappingError if there is no way to accomplish this"""
        if href == EndDeviceListUri:
            return (SubscriptionResource.SITE, None, None)

        # Try Reading
        result = parse(ReadingListUri, href)
        if result and result["reading_set_id"] == READING_SET_ALL_ID:
            try:
                return (
                    SubscriptionResource.READING,
                    int(result["site_id"]),
                    int(result["site_reading_type_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a Reading resource")

        # Try Rate
        result = parse(RateComponentListUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.TARIFF_GENERATED_RATE,
                    int(result["site_id"]),
                    int(result["tariff_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a Rate resource")

        # Try DOE
        result = parse(DERControlListUri, href)
        if result and result["der_program_id"] == DOE_PROGRAM_ID:
            try:
                return (SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE, int(result["site_id"]), None)
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DOE resource")

        # Try EndDevice
        result = parse(EndDeviceUri, href)
        if result:
            try:
                return (SubscriptionResource.SITE, int(result["site_id"]), None)
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a EndDevice resource")

        raise InvalidMappingError(f"Unable to interpret {href} as valid subscription resource")

    @staticmethod
    def map_from_request(
        subscription: Sep2Subscription,
        rs_params: RequestStateParameters,
        aggregator_domains: set[str],
        changed_time: datetime,
    ) -> Subscription:
        """Takes a sep2 subscription request and maps it to an internal Subscription. If the subscription
        is for an unsupported resource an InvalidMappingError will be raised

        subscription: The sep2 Subscription to be mapped
        aggregator_domains: The set of FQDN's controlled by Aggregator"""

        # Figure out what the client wants to subscribe to
        resource_href = remove_href_prefix(subscription.subscribedResource, rs_params)
        (resource, scoped_site_id, resource_id) = SubscriptionMapper.parse_resource_href(resource_href)

        try:
            uri = urlparse(subscription.notificationURI)
        except Exception as ex:
            raise InvalidMappingError(f"Error validating notificationURI: {ex}")

        # Dont allow adding webhooks to arbitrary domains
        if uri.hostname not in aggregator_domains:
            raise InvalidMappingError(
                f"Subscription URI has host {uri.hostname} which does NOT match aggregator FQDNs: {aggregator_domains}"
            )

        conditions: list[SubscriptionCondition]
        if subscription.condition:
            conditions = [
                SubscriptionCondition(
                    attribute=subscription.condition.attributeIdentifier,
                    lower_threshold=subscription.condition.lowerThreshold,
                    upper_threshold=subscription.condition.upperThreshold,
                )
            ]
        else:
            conditions = []

        return Subscription(
            aggregator_id=rs_params.aggregator_id,
            changed_time=changed_time,
            resource_type=resource,
            resource_id=resource_id,
            scoped_site_id=scoped_site_id,
            notification_uri=subscription.notificationURI,
            entity_limit=subscription.limit,
            conditions=conditions,
        )


class SubscriptionListMapper:
    @staticmethod
    def map_to_site_response(
        rs_params: RequestStateParameters, site_id: int, sub_list: Sequence[Subscription], sub_count: int
    ) -> SubscriptionListResponse:
        return SubscriptionListResponse.model_validate(
            {
                "href": generate_href(SubscriptionListUri, rs_params, site_id=site_id),
                "all_": sub_count,
                "results": len(sub_list),
                "subscriptions": [SubscriptionMapper.map_to_response(sub, rs_params) for sub in sub_list],
            }
        )


class NotificationMapper:

    @staticmethod
    def map_sites_to_response(
        sites: Sequence[Site], sub: Subscription, rs_params: RequestStateParameters
    ) -> Notification:
        """Turns a list of sites into a notification"""
        return Notification.model_validate(
            {
                "subscribedResource": generate_href(EndDeviceListUri, rs_params),
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, rs_params),
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
        doe_list_href = generate_href(DERControlListUri, rs_params, site_id=site_id, der_program_id=DOE_PROGRAM_ID)
        return Notification.model_validate(
            {
                "subscribedResource": doe_list_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, rs_params),
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
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, rs_params),
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
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, rs_params),
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
