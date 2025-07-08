from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

from envoy_schema.admin.schema.site import DERAvailability, DERConfiguration, DERControlType, DERStatus
from envoy_schema.admin.schema.site import SiteGroup as AdminSiteGroup
from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse
from envoy_schema.server.schema.sep2.der import DERType, DOESupportedMode

from envoy.server.mapper.common import pow10_to_decimal_value
from envoy.server.model.site import Site, SiteDERAvailability, SiteDERRating, SiteDERSetting, SiteDERStatus, SiteGroup


def _extract_failover_pow10_value(
    rating: Optional[SiteDERRating], setting: Optional[SiteDERSetting], value_name: str, multiplier_name: str
) -> Optional[Decimal]:
    """Internal utility for extracting a value from setting (if set) or failing over to rating otherwise"""
    setting_value: Optional[int] = None
    setting_multiplier: Optional[int] = None
    if setting:
        setting_value = getattr(setting, value_name)
        setting_multiplier = getattr(setting, multiplier_name)

        value = pow10_to_decimal_value(setting_value, setting_multiplier)
        if value is not None:
            return value

    if rating:
        rating_value = getattr(rating, value_name)
        rating_multiplier = getattr(rating, multiplier_name)

        return pow10_to_decimal_value(rating_value, rating_multiplier)

    return None


class SiteMapper:
    @staticmethod
    def map_to_der_status_response(status: Optional[SiteDERStatus]) -> Optional[DERStatus]:
        if status is None:
            return None

        return DERStatus(
            created_time=status.created_time,
            changed_time=status.changed_time,
            alarm_status=status.alarm_status,
            generator_connect_status=status.generator_connect_status,
            generator_connect_status_time=status.generator_connect_status_time,
            inverter_status=status.inverter_status,
            inverter_status_time=status.inverter_status_time,
            local_control_mode_status=status.local_control_mode_status,
            local_control_mode_status_time=status.local_control_mode_status_time,
            manufacturer_status=status.manufacturer_status,
            manufacturer_status_time=status.manufacturer_status_time,
            operational_mode_status=status.operational_mode_status,
            operational_mode_status_time=status.operational_mode_status_time,
        )

    @staticmethod
    def map_to_der_availability_response(availability: Optional[SiteDERAvailability]) -> Optional[DERAvailability]:
        if availability is None:
            return None

        return DERAvailability(
            created_time=availability.created_time,
            changed_time=availability.changed_time,
            availability_duration_sec=availability.availability_duration_sec,
            max_charge_duration_sec=availability.max_charge_duration_sec,
            reserved_charge_percent=availability.reserved_charge_percent,
            reserved_deliver_percent=availability.reserved_deliver_percent,
            estimated_var_avail=pow10_to_decimal_value(
                availability.estimated_var_avail_value, availability.estimated_var_avail_multiplier
            ),
            estimated_w_avail=pow10_to_decimal_value(
                availability.estimated_w_avail_value, availability.estimated_w_avail_multiplier
            ),
        )

    @staticmethod
    def map_to_der_config_response(
        rating: Optional[SiteDERRating], setting: Optional[SiteDERSetting]
    ) -> Optional[DERConfiguration]:
        """Maps a DER Rating / Setting  associated with a site into a single DERConfiguration. Values from setting
        will be preferenced over values from rating"""

        changed_time: Optional[datetime] = None
        created_time: Optional[datetime] = None
        modes_supported: Optional[DERControlType] = None

        if rating:
            created_time = rating.created_time
            changed_time = rating.changed_time
            if rating.modes_supported is not None:
                modes_supported = rating.modes_supported

        if setting:
            created_time = setting.created_time
            changed_time = setting.changed_time
            if setting.modes_enabled is not None:
                modes_supported = setting.modes_enabled

        if changed_time is None or created_time is None:
            # If setting and rating aren't set - just return None
            return None

        if modes_supported is None:
            modes_supported = DERControlType(0)

        doe_modes: DOESupportedMode = DOESupportedMode(0)
        if setting and setting.doe_modes_enabled is not None:
            doe_modes = setting.doe_modes_enabled
        elif rating and rating.doe_modes_supported is not None:
            doe_modes = rating.doe_modes_supported

        max_w = _extract_failover_pow10_value(rating, setting, "max_w_value", "max_w_multiplier")
        if max_w is None:
            # This should never happen as max_w is mandatory on setting and rating
            raise Exception(f"max_w couldn't be extracted for {setting} and {rating}")

        return DERConfiguration(
            # Mandatory
            created_time=created_time,
            changed_time=changed_time,
            modes_supported=modes_supported,
            type=rating.der_type if rating else DERType.NOT_APPLICABLE,
            doe_modes_supported=doe_modes,
            max_w=max_w,
            # Optional
            abnormal_category=rating.abnormal_category if rating else None,
            normal_category=rating.normal_category if rating else None,
            max_a=_extract_failover_pow10_value(rating, setting, "max_a_value", "max_a_multiplier"),
            max_ah=_extract_failover_pow10_value(rating, setting, "max_ah_value", "max_ah_multiplier"),
            max_charge_rate_va=_extract_failover_pow10_value(
                rating, setting, "max_charge_rate_va_value", "max_charge_rate_va_multiplier"
            ),
            max_charge_rate_w=_extract_failover_pow10_value(
                rating, setting, "max_charge_rate_w_value", "max_charge_rate_w_multiplier"
            ),
            max_discharge_rate_va=_extract_failover_pow10_value(
                rating, setting, "max_discharge_rate_va_value", "max_discharge_rate_va_multiplier"
            ),
            max_discharge_rate_w=_extract_failover_pow10_value(
                rating, setting, "max_discharge_rate_w_value", "max_discharge_rate_w_multiplier"
            ),
            max_v=_extract_failover_pow10_value(rating, setting, "max_v_value", "max_v_multiplier"),
            min_v=_extract_failover_pow10_value(rating, setting, "min_v_value", "min_v_multiplier"),
            max_va=_extract_failover_pow10_value(rating, setting, "max_va_value", "max_va_multiplier"),
            max_var=_extract_failover_pow10_value(rating, setting, "max_var_value", "max_var_multiplier"),
            max_var_neg=_extract_failover_pow10_value(rating, setting, "max_var_neg_value", "max_var_neg_multiplier"),
            max_wh=_extract_failover_pow10_value(rating, setting, "max_wh_value", "max_wh_multiplier"),
            v_nom=_extract_failover_pow10_value(rating, setting, "v_nom_value", "v_nom_multiplier"),
        )

    @staticmethod
    def map_to_site_response(site: Site) -> SiteResponse:
        """Maps our internal Site model to an equivalent SiteResponse. It's expected that site has their
        groups included"""

        if site.assignments:
            site_groups = [
                AdminSiteGroup(
                    site_group_id=a.group.site_group_id,
                    name=a.group.name,
                    created_time=a.group.created_time,
                    changed_time=a.group.changed_time,
                )
                for a in site.assignments
                if a.group
            ]
        else:
            site_groups = []

        rating: Optional[SiteDERRating] = None
        setting: Optional[SiteDERSetting] = None
        availability: Optional[SiteDERAvailability] = None
        status: Optional[SiteDERStatus] = None
        if site.site_ders:
            site_der = site.site_ders[0]
            if site_der:
                rating = site_der.site_der_rating
                setting = site_der.site_der_setting
                availability = site_der.site_der_availability
                status = site_der.site_der_status

        return SiteResponse(
            aggregator_id=site.aggregator_id,
            site_id=site.site_id,
            nmi=site.nmi,
            timezone_id=site.timezone_id,
            created_time=site.created_time,
            changed_time=site.changed_time,
            lfdi=site.lfdi,
            sfdi=site.sfdi,
            device_category=site.device_category,
            groups=site_groups,
            post_rate_seconds=site.post_rate_seconds,
            der_availability=SiteMapper.map_to_der_availability_response(availability),
            der_config=SiteMapper.map_to_der_config_response(rating, setting),
            der_status=SiteMapper.map_to_der_status_response(status),
        )

    @staticmethod
    def map_to_response(
        total_count: int, limit: int, start: int, group: Optional[str], after: Optional[datetime], sites: Iterable[Site]
    ) -> SitePageResponse:
        """Maps a set of sites to a single SitePageResponse. It's expected that sites will have their groups included"""
        return SitePageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            after=after,
            group=group,
            sites=[SiteMapper.map_to_site_response(s) for s in sites],
        )


class SiteGroupMapper:
    @staticmethod
    def map_to_site_group_response(group: SiteGroup, site_count: int) -> SiteGroupResponse:
        """Maps our internal SiteGroup model to an equivalent SiteResponse"""
        return SiteGroupResponse(
            site_group_id=group.site_group_id,
            name=group.name,
            created_time=group.created_time,
            changed_time=group.changed_time,
            total_sites=site_count,
        )

    @staticmethod
    def map_to_response(
        total_count: int, limit: int, start: int, site_groups_with_count: Iterable[tuple[SiteGroup, int]]
    ) -> SiteGroupPageResponse:
        """Maps a set of sites to a single SitePageResponse"""
        return SiteGroupPageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            groups=[SiteGroupMapper.map_to_site_group_response(g, count) for (g, count) in site_groups_with_count],
        )
