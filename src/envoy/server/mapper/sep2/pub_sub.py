from datetime import date, datetime
from enum import IntEnum
from typing import Optional, Sequence, Union
from urllib.parse import urlparse

from envoy_schema.server.schema.sep2.pub_sub import (
    XSI_TYPE_DEFAULT_DER_CONTROL,
    XSI_TYPE_DER_AVAILABILITY,
    XSI_TYPE_DER_CAPABILITY,
    XSI_TYPE_DER_CONTROL_LIST,
    XSI_TYPE_DER_PROGRAM_LIST,
    XSI_TYPE_DER_SETTINGS,
    XSI_TYPE_DER_STATUS,
    XSI_TYPE_END_DEVICE_LIST,
    XSI_TYPE_FUNCTION_SET_ASSIGNMENTS_LIST,
    XSI_TYPE_READING_LIST,
    XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
)
from envoy_schema.server.schema.sep2.pub_sub import Condition as Sep2Condition
from envoy_schema.server.schema.sep2.pub_sub import Notification, NotificationStatus
from envoy_schema.server.schema.sep2.pub_sub import Subscription as Sep2Subscription
from envoy_schema.server.schema.sep2.pub_sub import SubscriptionEncoding, SubscriptionListResponse
from envoy_schema.server.schema.uri import (
    DefaultDERControlUri,
    DERAvailabilityUri,
    DERCapabilityUri,
    DERControlListUri,
    DERProgramFSAListUri,
    DERProgramListUri,
    DERSettingsUri,
    DERStatusUri,
    EndDeviceListUri,
    EndDeviceUri,
    FunctionSetAssignmentsListUri,
    RateComponentListUri,
    ReadingListUri,
    SubscriptionListUri,
    SubscriptionUri,
    TimeTariffIntervalListUri,
)
from parse import parse  # type: ignore

from envoy.server.crud.site import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.exception import InvalidMappingError
from envoy.server.manager.time import utc_now
from envoy.server.mapper.common import generate_href, remove_href_prefix
from envoy.server.mapper.constants import PricingReadingType
from envoy.server.mapper.csip_aus.doe import DefaultDERControl, DERControlMapper, DERProgramMapper
from envoy.server.mapper.sep2.der import DERAvailabilityMapper, DERCapabilityMapper, DERSettingMapper, DERStatusMapper
from envoy.server.mapper.sep2.end_device import EndDeviceMapper
from envoy.server.mapper.sep2.function_set_assignments import FunctionSetAssignmentsMapper
from envoy.server.mapper.sep2.metering import READING_SET_ALL_ID, MirrorMeterReadingMapper
from envoy.server.mapper.sep2.pricing import TimeTariffIntervalMapper
from envoy.server.model.archive.doe import ArchiveDynamicOperatingEnvelope, ArchiveSiteControlGroup
from envoy.server.model.doe import DynamicOperatingEnvelope, SiteControlGroup, SiteControlGroupDefault
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus
from envoy.server.model.site_reading import SiteReading
from envoy.server.model.subscription import Subscription, SubscriptionCondition, SubscriptionResource
from envoy.server.model.tariff import TariffGeneratedRate
from envoy.server.request_scope import AggregatorRequestScope


class NotificationType(IntEnum):
    """Why is a notification being raised for an entity?"""

    ENTITY_CHANGED = 1  # Raised when an entity has changed in place (same mrid/href)
    ENTITY_DELETED = 2  # Raised when an entity has deleted entirely (old mrid/href no longer exists)


def _map_to_notification_status(nt: NotificationType) -> NotificationStatus:
    if nt == NotificationType.ENTITY_CHANGED:
        return NotificationStatus.DEFAULT
    elif nt == NotificationType.ENTITY_DELETED:
        return NotificationStatus.SUBSCRIPTION_CANCELLED_RESOURCE_DELETED
    else:
        raise ValueError(f"NotificationType {nt} is not supported")


def _parse_site_id_from_match(raw_site_id: str) -> Optional[int]:
    site_id = int(raw_site_id)
    return site_id if site_id != VIRTUAL_END_DEVICE_SITE_ID else None


class SubscriptionMapper:
    @staticmethod
    def calculate_subscription_href(sub: Subscription, scope: AggregatorRequestScope) -> str:
        """Calculates the href for a subscription - this will vary depending on whether the subscription
        is narrowed to a particular end_device or is unscoped"""
        return generate_href(SubscriptionUri, scope, site_id=scope.display_site_id, subscription_id=sub.subscription_id)

    @staticmethod
    def calculate_resource_href(sub: Subscription, scope: AggregatorRequestScope) -> str:  # noqa C901
        """Calculates the href for a Subscription.subscribedResource based on what the subscription is tracking

        Some combos of resource_type/scoped_site_id/resource_id may be invalid and will raise InvalidMappingError"""
        href_site_id = sub.scoped_site_id if sub.scoped_site_id is not None else scope.display_site_id

        if sub.resource_type == SubscriptionResource.SITE:
            if sub.scoped_site_id is None:
                return generate_href(EndDeviceListUri, scope)
            else:
                return generate_href(EndDeviceUri, scope, site_id=href_site_id)
        elif sub.resource_type == SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE:
            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to DOEs without a resource_id is unsupported on sub {sub.subscription_id}"
                )

            return generate_href(DERControlListUri, scope, site_id=href_site_id, der_program_id=sub.resource_id)
        elif sub.resource_type == SubscriptionResource.READING:
            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to readings without a resource_id is unsupported on sub {sub.subscription_id}"
                )

            return generate_href(
                ReadingListUri,
                scope,
                site_id=href_site_id,
                site_reading_type_id=sub.resource_id,
                reading_set_id=READING_SET_ALL_ID,
            )
        elif sub.resource_type == SubscriptionResource.TARIFF_GENERATED_RATE:
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
                scope,
                site_id=href_site_id,
                tariff_id=sub.resource_id,
            )
        elif sub.resource_type == SubscriptionResource.SITE_DER_AVAILABILITY:
            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to DERAvailability requires resource_id on sub {sub.subscription_id}"
                )

            return generate_href(DERAvailabilityUri, scope, site_id=href_site_id, der_id=sub.resource_id)
        elif sub.resource_type == SubscriptionResource.SITE_DER_RATING:

            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to DERCapability requires resource_id on sub {sub.subscription_id}"
                )

            return generate_href(DERCapabilityUri, scope, site_id=href_site_id, der_id=sub.resource_id)
        elif sub.resource_type == SubscriptionResource.SITE_DER_SETTING:

            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to DERSettings requires resource_id on sub {sub.subscription_id}"
                )

            return generate_href(DERSettingsUri, scope, site_id=href_site_id, der_id=sub.resource_id)
        elif sub.resource_type == SubscriptionResource.SITE_DER_STATUS:

            if sub.resource_id is None:
                raise InvalidMappingError(f"Subscribing to DERStatus requires resource_id on sub {sub.subscription_id}")

            return generate_href(DERStatusUri, scope, site_id=href_site_id, der_id=sub.resource_id)
        elif sub.resource_type == SubscriptionResource.DEFAULT_SITE_CONTROL:

            if sub.resource_id is None:
                raise InvalidMappingError(
                    f"Subscribing to DefaultDERControl requires resource_id on sub {sub.subscription_id}"
                )

            return generate_href(DefaultDERControlUri, scope, site_id=href_site_id, der_program_id=sub.resource_id)
        elif sub.resource_type == SubscriptionResource.FUNCTION_SET_ASSIGNMENTS:
            return generate_href(FunctionSetAssignmentsListUri, scope, site_id=href_site_id)
        elif sub.resource_type == SubscriptionResource.SITE_CONTROL_GROUP:
            if sub.resource_id is not None:
                return generate_href(DERProgramFSAListUri, scope, site_id=href_site_id, fsa_id=sub.resource_id)
            else:
                return generate_href(DERProgramListUri, scope, site_id=href_site_id)
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
    def map_to_response(sub: Subscription, scope: AggregatorRequestScope) -> Sep2Subscription:
        """Maps an internal Subscription model to the Sep2 model Equivalent"""
        condition: Optional[Sep2Condition] = None
        if sub.conditions and len(sub.conditions) > 0:
            condition = SubscriptionMapper.map_to_response_condition(sub.conditions[0])

        return Sep2Subscription.model_validate(
            {
                "href": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "encoding": SubscriptionEncoding.XML,
                "level": "+S1",
                "limit": sub.entity_limit,
                "notificationURI": sub.notification_uri,
                "subscribedResource": SubscriptionMapper.calculate_resource_href(sub, scope),
                "condition": condition,
            }
        )

    @staticmethod
    def parse_resource_href(href: str) -> tuple[SubscriptionResource, Optional[int], Optional[int]]:  # noqa C901
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
                    _parse_site_id_from_match(result["site_id"]),
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
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["tariff_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a Rate resource")

        # Try DOE
        result = parse(DERControlListUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.DYNAMIC_OPERATING_ENVELOPE,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["der_program_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DOE resource")

        # Try DERAvailability
        result = parse(DERAvailabilityUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.SITE_DER_AVAILABILITY,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["der_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DERAvailability resource")

        # Try DERCapability
        result = parse(DERCapabilityUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.SITE_DER_RATING,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["der_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DERRating resource")

        # Try DERSetting
        result = parse(DERSettingsUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.SITE_DER_SETTING,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["der_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DERSetting resource")

        # Try DERStatus
        result = parse(DERStatusUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.SITE_DER_STATUS,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["der_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DERStatus resource")

        # Try DefaultDERControl
        result = parse(DefaultDERControlUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.DEFAULT_SITE_CONTROL,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["der_program_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DefaultDERControl resource")

        # Try DERProgramList (FSA scoped)
        result = parse(DERProgramFSAListUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.SITE_CONTROL_GROUP,
                    _parse_site_id_from_match(result["site_id"]),
                    int(result["fsa_id"]),
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DERProgramListUri resource")

        # Try FunctionSetAssignmentsList
        result = parse(FunctionSetAssignmentsListUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.FUNCTION_SET_ASSIGNMENTS,
                    _parse_site_id_from_match(result["site_id"]),
                    None,
                )
            except ValueError:
                raise InvalidMappingError(
                    f"Unable to interpret {href} parsed {result} as a FunctionSetAssignmentList resource"
                )

        # Try DERProgramList
        result = parse(DERProgramListUri, href)
        if result:
            try:
                return (
                    SubscriptionResource.SITE_CONTROL_GROUP,
                    _parse_site_id_from_match(result["site_id"]),
                    None,
                )
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a DERProgramListUri resource")

        # Try EndDevice
        result = parse(EndDeviceUri, href)
        if result:
            try:
                return (SubscriptionResource.SITE, _parse_site_id_from_match(result["site_id"]), None)
            except ValueError:
                raise InvalidMappingError(f"Unable to interpret {href} parsed {result} as a EndDevice resource")

        raise InvalidMappingError(f"Unable to interpret {href} as valid subscription resource")

    @staticmethod
    def map_from_request(
        subscription: Sep2Subscription,
        scope: AggregatorRequestScope,
        aggregator_domains: set[str],
        changed_time: datetime,
    ) -> Subscription:
        """Takes a sep2 subscription request and maps it to an internal Subscription. If the subscription
        is for an unsupported resource an InvalidMappingError will be raised

        subscription: The sep2 Subscription to be mapped
        aggregator_domains: The set of FQDN's controlled by Aggregator"""

        # Figure out what the client wants to subscribe to
        resource_href = remove_href_prefix(subscription.subscribedResource, scope)
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
            aggregator_id=scope.aggregator_id,
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
        scope: AggregatorRequestScope, sub_list: Sequence[Subscription], sub_count: int
    ) -> SubscriptionListResponse:
        return SubscriptionListResponse.model_validate(
            {
                "href": generate_href(SubscriptionListUri, scope, site_id=scope.display_site_id),
                "all_": sub_count,
                "results": len(sub_list),
                "subscriptions": [SubscriptionMapper.map_to_response(sub, scope) for sub in sub_list],
            }
        )


class NotificationMapper:

    @staticmethod
    def map_sites_to_response(
        sites: Sequence[Site],
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
        disable_registration: bool,
        poll_rate_seconds: int,
    ) -> Notification:
        """Turns a list of sites into a notification"""
        edev_list_href = generate_href(EndDeviceListUri, scope)
        return Notification.model_validate(
            {
                "subscribedResource": generate_href(EndDeviceListUri, scope),
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": {
                    "type": XSI_TYPE_END_DEVICE_LIST,
                    "href": edev_list_href,
                    "pollRate": poll_rate_seconds,
                    "all_": len(sites),
                    "results": len(sites),
                    "EndDevice": [EndDeviceMapper.map_to_response(scope, s, disable_registration, 0) for s in sites],
                },
            }
        )

    @staticmethod
    def map_does_to_response(
        site_control_group_id: int,
        does: Sequence[Union[DynamicOperatingEnvelope, ArchiveDynamicOperatingEnvelope]],
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
        power10_multiplier: int,
    ) -> Notification:
        """Turns a list of does into a notification"""
        doe_list_href = generate_href(
            DERControlListUri, scope, site_id=scope.display_site_id, der_program_id=site_control_group_id
        )
        now = utc_now()
        return Notification.model_validate(
            {
                "subscribedResource": doe_list_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": {
                    "type": XSI_TYPE_DER_CONTROL_LIST,
                    "href": doe_list_href,
                    "all_": len(does),
                    "results": len(does),
                    "DERControl": [
                        DERControlMapper.map_to_response(scope, site_control_group_id, d, power10_multiplier, now)
                        for d in does
                    ],
                },
            }
        )

    @staticmethod
    def map_site_control_groups_to_response(
        site_control_groups: Sequence[Union[SiteControlGroup, ArchiveSiteControlGroup]],
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a list of does into a notification"""
        group_list_href = generate_href(DERProgramListUri, scope, site_id=scope.display_site_id)
        return Notification.model_validate(
            {
                "subscribedResource": group_list_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": {
                    "type": XSI_TYPE_DER_PROGRAM_LIST,
                    "href": group_list_href,
                    "all_": len(site_control_groups),
                    "results": len(site_control_groups),
                    "DERProgram": [
                        DERProgramMapper.doe_program_response(scope, None, scg, None) for scg in site_control_groups
                    ],
                },
            }
        )

    @staticmethod
    def map_readings_to_response(
        mup_id: int,
        readings: Sequence[SiteReading],
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a list of does into a notification"""
        reading_list_href = generate_href(
            ReadingListUri,
            scope,
            site_id=scope.display_site_id,
            site_reading_type_id=mup_id,
            reading_set_id=READING_SET_ALL_ID,  # Can't correlate this back to anything else - all will be fine
        )
        return Notification.model_validate(
            {
                "subscribedResource": reading_list_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": {
                    "type": XSI_TYPE_READING_LIST,
                    "href": reading_list_href,
                    "all_": len(readings),
                    "results": len(readings),
                    "Readings": [MirrorMeterReadingMapper.map_to_response(r) for r in readings],
                },
            }
        )

    @staticmethod
    def map_rates_to_response(
        tariff_id: int,
        day: date,
        pricing_reading_type: PricingReadingType,
        rates: Sequence[TariffGeneratedRate],
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a list of dynamic prices into a notification"""
        time_tariff_interval_list_href = generate_href(
            TimeTariffIntervalListUri,
            scope,
            site_id=scope.display_site_id,
            tariff_id=tariff_id,
            rate_component_id=day.isoformat(),
            pricing_reading=int(pricing_reading_type),
        )
        return Notification.model_validate(
            {
                "subscribedResource": time_tariff_interval_list_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": {
                    "type": XSI_TYPE_TIME_TARIFF_INTERVAL_LIST,
                    "href": time_tariff_interval_list_href,
                    "all_": len(rates),
                    "results": len(rates),
                    "TimeTariffInterval": [
                        TimeTariffIntervalMapper.map_to_response(scope, r, pricing_reading_type) for r in rates
                    ],
                },
            }
        )

    @staticmethod
    def map_der_availability_to_response(
        der_id: int,
        der_availability: Optional[SiteDERAvailability],
        der_availability_site_id: int,
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a single SiteDERAvailability into a notification."""
        der_avail_href = generate_href(
            DERAvailabilityUri,
            scope,
            site_id=scope.display_site_id,
            der_id=der_id,
        )

        resource_model: Optional[dict] = None
        if der_availability is not None:
            # Easiest way to map entity to resource is via model_dump
            resource = DERAvailabilityMapper.map_to_response(scope, der_availability, der_availability_site_id)
            resource.type = XSI_TYPE_DER_AVAILABILITY
            resource_model = resource.model_dump()
        return Notification.model_validate(
            {
                "subscribedResource": der_avail_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": resource_model,
            }
        )

    @staticmethod
    def map_der_rating_to_response(
        der_id: int,
        der_rating: Optional[SiteDERRating],
        der_rating_site_id: int,
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a single SiteDERRating into a notification."""
        der_rating_href = generate_href(
            DERCapabilityUri,
            scope,
            site_id=scope.display_site_id,
            der_id=der_id,
        )

        resource_model: Optional[dict] = None
        if der_rating is not None:
            # Easiest way to map entity to resource is via model_dump
            resource = DERCapabilityMapper.map_to_response(scope, der_rating, der_rating_site_id)
            resource.type = XSI_TYPE_DER_CAPABILITY
            resource_model = resource.model_dump()
        return Notification.model_validate(
            {
                "subscribedResource": der_rating_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": resource_model,
            }
        )

    @staticmethod
    def map_der_settings_to_response(
        der_id: int,
        der_setting: Optional[SiteDERSetting],
        der_setting_site_id: int,
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a single SiteDERSetting into a notification."""
        der_settings_href = generate_href(
            DERSettingsUri,
            scope,
            site_id=scope.display_site_id,
            der_id=der_id,
        )

        resource_model: Optional[dict] = None
        if der_setting is not None:
            # Easiest way to map entity to resource is via model_dump
            resource = DERSettingMapper.map_to_response(scope, der_setting, der_setting_site_id)
            resource.type = XSI_TYPE_DER_SETTINGS
            resource_model = resource.model_dump()

        return Notification.model_validate(
            {
                "subscribedResource": der_settings_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": resource_model,
            }
        )

    @staticmethod
    def map_der_status_to_response(
        der_id: int,
        der_status: Optional[SiteDERStatus],
        der_status_site_id: int,
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a single SiteDERStatus into a notification."""
        der_status_href = generate_href(
            DERStatusUri,
            scope,
            site_id=scope.display_site_id,
            der_id=der_id,
        )

        resource_model: Optional[dict] = None
        if der_status is not None:
            # Easiest way to map entity to resource is via model_dump
            resource = DERStatusMapper.map_to_response(scope, der_status, der_status_site_id)
            resource.type = XSI_TYPE_DER_STATUS
            resource_model = resource.model_dump()

        return Notification.model_validate(
            {
                "subscribedResource": der_status_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": resource_model,
            }
        )

    @staticmethod
    def map_function_set_assignments_list_to_response(
        poll_rate_seconds: int,
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
        new_fsa_ids: list[int],
    ) -> Notification:
        """Turns a poll rate into a notification for a FunctionSetAssignmentsList"""

        fsa_list_href = generate_href(FunctionSetAssignmentsListUri, scope, site_id=scope.display_site_id)
        return Notification.model_validate(
            {
                "subscribedResource": fsa_list_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": {
                    "type": XSI_TYPE_FUNCTION_SET_ASSIGNMENTS_LIST,
                    "href": fsa_list_href,
                    "pollRate": poll_rate_seconds,
                    "all_": len(new_fsa_ids),
                    "results": len(new_fsa_ids),
                    "FunctionSetAssignments": [
                        FunctionSetAssignmentsMapper.map_to_response_unscoped(
                            scope, scope.display_site_id, fsa_id, None, None
                        )
                        for fsa_id in new_fsa_ids
                    ],
                },
            }
        )

    @staticmethod
    def map_default_site_control_response(
        scg_default: Optional[SiteControlGroupDefault],
        der_program_id: int,
        pow10_multipier: int,
        sub: Subscription,
        scope: AggregatorRequestScope,
        notification_type: NotificationType,
    ) -> Notification:
        """Turns a poll rate into a notification for a FunctionSetAssignmentsList"""

        default_der_control_href = generate_href(
            DefaultDERControlUri, scope, site_id=scope.display_site_id, der_program_id=der_program_id
        )

        resource_model: Optional[DefaultDERControl] = None
        if scg_default is not None:
            resource_model = DERControlMapper.map_to_default_response(
                scope, scg_default, scope.display_site_id, der_program_id, pow10_multipier
            )
            resource_model.type = XSI_TYPE_DEFAULT_DER_CONTROL

        return Notification.model_validate(
            {
                "subscribedResource": default_der_control_href,
                "subscriptionURI": SubscriptionMapper.calculate_subscription_href(sub, scope),
                "status": _map_to_notification_status(notification_type),
                "resource": resource_model.model_dump() if resource_model is not None else None,
            }
        )
