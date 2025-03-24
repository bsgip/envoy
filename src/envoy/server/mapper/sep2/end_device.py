from datetime import datetime
from typing import Optional, Sequence

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.end_device import (
    EndDeviceListResponse,
    EndDeviceRequest,
    EndDeviceResponse,
    RegistrationResponse,
)
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.types import SubscribableType

from envoy.server.crud.common import sum_digits
from envoy.server.mapper.common import generate_href, parse_device_category
from envoy.server.model.site import Site
from envoy.server.request_scope import BaseRequestScope
from envoy.server.settings import settings


class EndDeviceMapper:
    @staticmethod
    def map_to_response(scope: BaseRequestScope, site: Site) -> EndDeviceResponse:
        edev_href = generate_href(uri.EndDeviceUri, scope, site_id=site.site_id)
        fsa_href = generate_href(uri.FunctionSetAssignmentsListUri, scope, site_id=site.site_id)
        der_href = generate_href(uri.DERListUri, scope, site_id=site.site_id)
        pubsub_href = generate_href(uri.SubscriptionListUri, scope, site_id=site.site_id)
        registration_href = generate_href(uri.RegistrationUri, scope, site_id=site.site_id)
        logevent_href = generate_href(uri.LogEventListUri, scope, site_id=site.site_id)
        return EndDeviceResponse.model_validate(
            {
                "href": edev_href,
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "deviceCategory": f"{site.device_category:x}",  # deviceCategory is a hex string
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
                "ConnectionPointLink": ConnectionPointLink(href=edev_href + "/cp"),
                "DERListLink": ListLink(href=der_href, all_=1),  # Always a single DER
                "SubscriptionListLink": ListLink(href=pubsub_href),
                "FunctionSetAssignmentsListLink": ListLink(href=fsa_href),
                "RegistrationLink": Link(href=registration_href),
                "LogEventListLink": ListLink(href=logevent_href),
            }
        )

    @staticmethod
    def map_from_request(
        end_device: EndDeviceRequest, aggregator_id: int, changed_time: datetime, registration_pin: int
    ) -> Site:
        return Site(
            lfdi=end_device.lFDI,
            sfdi=end_device.sFDI,
            registration_pin=registration_pin,
            changed_time=changed_time,
            aggregator_id=aggregator_id,
            device_category=parse_device_category(end_device.deviceCategory),
            timezone_id=settings.default_timezone,
        )


class VirtualEndDeviceMapper:
    @staticmethod
    def map_to_response(scope: BaseRequestScope, site: Site) -> EndDeviceResponse:
        edev_href = generate_href(uri.EndDeviceUri, scope, site_id=site.site_id)
        pubsub_href = generate_href(uri.SubscriptionListUri, scope, site_id=site.site_id)
        return EndDeviceResponse.model_validate(
            {
                "href": edev_href,
                "lFDI": site.lfdi,
                "sFDI": site.sfdi,
                "subscribable": SubscribableType.resource_does_not_support_subscriptions,
                "deviceCategory": f"{site.device_category:x}",  # deviceCategory is a hex string
                "changedTime": int(site.changed_time.timestamp()),
                "enabled": True,
                "SubscriptionListLink": ListLink(href=pubsub_href),
            }
        )


class EndDeviceListMapper:
    @staticmethod
    def map_to_response(
        scope: BaseRequestScope,
        site_list: Sequence[Site],
        site_count: int,
        virtual_site: Optional[Site] = None,
    ) -> EndDeviceListResponse:

        end_devices = [EndDeviceMapper.map_to_response(scope, site) for site in site_list]
        result_count = len(end_devices)

        # Add the virtual site to the results if present
        if virtual_site:
            # The sites list needs to be sorted descending in changed_time.
            # The virtual site has a changed_time matching when the call to `get_virtual_site_for_aggregator` was made.
            # We assume the virtual site will *always* be the most recent site and therefore we add the
            # virtual site to the front of the list of sites.
            end_devices.insert(0, VirtualEndDeviceMapper.map_to_response(scope, virtual_site))
            result_count += 1

        return EndDeviceListResponse.model_validate(
            {
                "href": generate_href(uri.EndDeviceListUri, scope),
                "all_": site_count,
                "results": result_count,
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "EndDevice": end_devices,
            }
        )


class RegistrationMapper:
    @staticmethod
    def add_checksum_to_registration_pin(raw_pin: int) -> int:
        """Takes a 5 digit PIN and converts it to the sep2 version that includes a checksum digit based on the sum
        of digits.

        eg 12345 becomes  123455  (With the checksum being a base10 sum of digits which is then mod 10)"""
        checksum_digit = sum_digits(raw_pin) % 10
        return (raw_pin * 10) + checksum_digit

    @staticmethod
    def map_to_response(scope: BaseRequestScope, site: Site) -> RegistrationResponse:
        """Generates a RegistrationResponse for a single site"""
        href = generate_href(uri.RegistrationUri, scope, site_id=site.site_id)
        pin_with_checksum = RegistrationMapper.add_checksum_to_registration_pin(site.registration_pin)

        return RegistrationResponse(
            href=href, pIN=pin_with_checksum, dateTimeRegistered=int(site.created_time.timestamp())
        )
