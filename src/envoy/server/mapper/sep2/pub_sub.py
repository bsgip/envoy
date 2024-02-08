from typing import Optional, Sequence

from envoy_schema.server.schema.sep2.pub_sub import Notification, NotificationStatus
from envoy_schema.server.schema.uri import (
    EndDeviceListUri,
    SubscriptionGlobalUri,
    SubscriptionUri,
    TimeTariffIntervalListUri,
)

from envoy.server.api.request import RequestStateParameters
from envoy.server.mapper.common import generate_href
from envoy.server.mapper.sep2.end_device import EndDeviceMapper
from envoy.server.mapper.sep2.pricing import PricingReadingType
from envoy.server.model.site import Site
from envoy.server.model.subscription import Subscription
from envoy.server.model.tariff import TariffGeneratedRate


class NotificationMapper:
    @staticmethod
    def calculate_subscription_href(sub: Subscription) -> str:
        """Calculates the href for a subscription - this will vary depending on whether the subscription
        is narrowed to a particular end_device or is unscoped"""
        if sub.scoped_site_id is None:
            return SubscriptionGlobalUri.format(subscription_id=sub.subscription_id)
        else:
            return SubscriptionUri.format(site_id=sub.scoped_site_id, subscription_id=sub.subscription_id)

    @staticmethod
    def map_sites_to_response(sites: Sequence[Site], sub: Subscription, href_prefix: Optional[str]) -> Notification:
        """Turns a list of sites into a notification"""
        rs_params = RequestStateParameters(sub.aggregator_id, href_prefix)
        return Notification.model_validate(
            {
                "subscribedResource": generate_href(EndDeviceListUri, rs_params),
                "subscriptionURI": NotificationMapper.calculate_subscription_href(sub),
                "status": NotificationStatus.DEFAULT,
                "resource": {
                    "type": "EndDeviceList",
                    "all_": len(sites),
                    "results": len(sites),
                    "EndDevice": [EndDeviceMapper.map_to_response(rs_params, s) for s in sites],
                },
            }
        )

    @staticmethod
    def map_rates_to_response(
        pricing_reading_type: PricingReadingType,
        site_id: int,
        rates: Sequence[TariffGeneratedRate],
        sub: Subscription,
        href_prefix: Optional[str],
    ) -> Notification:
        """Turns a list of dynamic prices into a notification"""
        # TimeTariffIntervalListUri = "/edev/{site_id}/tp/{tariff_id}/rc/{rate_component_id}/{pricing_reading}/tti"
        rs_params = RequestStateParameters(sub.aggregator_id, href_prefix)
        tti_href = generate_href(TimeTariffIntervalListUri, rs_params, site_id=site_id, tariff_id=)
        return Notification.model_validate(
            {
                "subscribedResource": TimeTariffIntervalListUri,
                "subscriptionURI": NotificationMapper.calculate_subscription_href(sub),
                "status": NotificationStatus.DEFAULT,
                "resource": {
                    "type": "TimeTariffIntervalList",
                    "all_": len(rates),
                    "results": len(rates),
                    "EndDevice": [EndDeviceMapper.map_to_response(rs_params, s) for s in sites],
                },
            }
        )
