from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Protocol, Sequence, Union, cast

import envoy_schema.server.schema.uri as uri
from envoy_schema.server.schema.csip_aus.connection_point import ConnectionPointLink
from envoy_schema.server.schema.sep2.der import (
    DER,
    AlarmStatusType,
    ConnectStatusType,
    DERAvailability,
    DERCapability,
    DERControlType,
    DERListResponse,
    DERSettings,
    DERStatus,
)
from envoy_schema.server.schema.sep2.der_control_types import ActivePower, PowerFactor, ReactivePower
from envoy_schema.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceRequest, EndDeviceResponse
from envoy_schema.server.schema.sep2.identification import Link, ListLink
from envoy_schema.server.schema.sep2.types import DEVICE_CATEGORY_ALL_SET, DeviceCategory, SubscribableType

from envoy.server.exception import InvalidMappingError
from envoy.server.mapper.common import generate_href
from envoy.server.model.site import (
    PERCENT_DECIMAL_POWER,
    Site,
    SiteDER,
    SiteDERAvailability,
    SiteDERRating,
    SiteDERStatus,
)
from envoy.server.request_state import RequestStateParameters
from envoy.server.settings import settings


class ValueMultiplier(Protocol):
    """Protocol that captures ActivePower/ReactivePower and other similar types"""

    value: int
    multiplier: int


class DisplacementMultiplier(Protocol):
    """Protocol that captures ActivePower/ReactivePower and other similar types"""

    displacement: int
    multiplier: int


def get_value_multiplier(value: Optional[int], multiplier: Optional[int], value_name: str = "value") -> Optional[dict]:
    """Utility for setting {"value": X, "multiplier": Y} pydantic models that is a nice
    shorthand for populating a variety of DER data types (eg ActivePower/ReactivePower)"""
    if value is not None and multiplier is not None:
        return {value_name: value, "multiplier": multiplier}
    return None


def set_value_multiplier(
    vm: Union[Optional[ValueMultiplier], Optional[DisplacementMultiplier]]
) -> tuple[Optional[int], Optional[int]]:
    """Utility for undoing get_value_multiplier. Returns the value|displacement / multiplier
    for the specified vm that should allow a quick shorthand for setting the values back
    on a DB model"""
    if vm is None:
        return (None, None)

    if hasattr(vm, "value"):
        return (vm.value, vm.multiplier)
    else:
        return (vm.displacement, vm.multiplier)


def to_sep2_percent(d: Optional[Decimal]) -> Optional[int]:
    if d is None:
        return None
    return int(d * PERCENT_DECIMAL_POWER)


def from_sep2_percent(v: Optional[int]) -> Optional[Decimal]:
    if v is None:
        return None
    return Decimal(v) / PERCENT_DECIMAL_POWER


def to_hex_binary(v: Optional[int]) -> Optional[str]:
    if v is None:
        return None

    return f"{v:0x}"  # hex encoded


class DERMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, der: SiteDER, active_derp_id: Optional[str]) -> DER:
        der_href = generate_href(uri.DERUri, rs_params, site_id=der.site_id, der_id=der.site_der_id)
        current_derp_link: Optional[Link] = None
        if active_derp_id:
            current_derp_link = Link.model_validate(
                {
                    "href": generate_href(
                        uri.DERProgramUri, rs_params, site_id=der.site_id, der_program_id=active_derp_id
                    )
                }
            )

        return DER.model_validate(
            {
                "href": der_href,
                "AssociatedDERProgramListLink": {
                    "href": generate_href(
                        uri.AssociatedDERProgramListUri, rs_params, site_id=der.site_id, der_program_id=active_derp_id
                    )
                },
                "CurrentDERProgramLink": current_derp_link,
                "DERStatusLink": {
                    "href": generate_href(
                        uri.DERStatusUri, rs_params, site_id=der.site_id, der_program_id=active_derp_id
                    )
                },
                "DERCapabilityLink": {
                    "href": generate_href(
                        uri.DERCapabilityUri, rs_params, site_id=der.site_id, der_program_id=active_derp_id
                    )
                },
                "DERSettingsLink": {
                    "href": generate_href(
                        uri.DERSettingsUri, rs_params, site_id=der.site_id, der_program_id=active_derp_id
                    )
                },
                "DERAvailabilityLink": {
                    "href": generate_href(
                        uri.DERAvailabilityUri, rs_params, site_id=der.site_id, der_program_id=active_derp_id
                    )
                },
            }
        )

    @staticmethod
    def map_to_list_response(
        rs_params: RequestStateParameters,
        site_id: int,
        poll_rate_seconds: int,
        ders_with_act_derp_id: list[tuple[SiteDER, Optional[str]]],
        der_count: int,
    ) -> DERListResponse:
        """Turns a set of SiteDER (with their active DER program ID) into a list response

        ders_with_act_derp_id: SiteDER tupled with the Active DER Program ID for that SiteDER (if any)"""
        return DERListResponse.model_validate(
            {
                "href": generate_href(uri.DERListUri, rs_params, site_id=site_id),
                "poll_rate": poll_rate_seconds,
                "all_": der_count,
                "results": len(ders_with_act_derp_id),
                "DER_": [
                    DERMapper.map_to_response(rs_params, e, act_derp_id) for e, act_derp_id in ders_with_act_derp_id
                ],
            }
        )


class DERAvailabilityMapper:
    @staticmethod
    def map_to_response(
        rs_params: RequestStateParameters, site_id: int, der_avail: SiteDERAvailability
    ) -> DERAvailability:
        return DERAvailability.model_validate(
            {
                "href": generate_href(uri.DERAvailabilityUri, rs_params, site_id=site_id, der_id=der_avail.site_der_id),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "availabilityDuration": der_avail.availability_duration_sec,
                "maxChargeDuration": der_avail.max_charge_duration_sec,
                "readingTime": int(der_avail.changed_time.timestamp()),
                "reserveChargePercent": to_sep2_percent(der_avail.reserved_charge_percent),
                "reservePercent": to_sep2_percent(der_avail.reserved_deliver_percent),
                "statVarAvail": get_value_multiplier(
                    der_avail.estimated_var_avail_value, der_avail.estimated_var_avail_multiplier
                ),
                "statWAvail": get_value_multiplier(
                    der_avail.estimated_w_avail_value, der_avail.estimated_w_avail_multiplier
                ),
            }
        )

    @staticmethod
    def map_from_request(changed_time: datetime, der_avail: DERAvailability) -> SiteDERAvailability:
        m = SiteDERAvailability(
            availability_duration_sec=der_avail.availabilityDuration,
            max_charge_duration_sec=der_avail.maxChargeDuration,
            changed_time=changed_time,
            reserved_charge_percent=from_sep2_percent(der_avail.reserveChargePercent),
            reserved_deliver_percent=from_sep2_percent(der_avail.reservePercent),
        )
        (m.estimated_var_avail_value, m.estimated_var_avail_multiplier) = set_value_multiplier(der_avail.statVarAvail)
        (m.estimated_w_avail_value, m.estimated_w_avail_multiplier) = set_value_multiplier(der_avail.statWAvail)
        return m


class DERStatusMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, site_id: int, der_status: SiteDERStatus) -> DERStatus:
        changed_timestamp = int(der_status.changed_time.timestamp())

        gen_conn_status: Optional[dict] = None
        if der_status.generator_connect_status is not None and der_status.generator_connect_status_time is not None:
            gen_conn_status = {
                "value": to_hex_binary(der_status.generator_connect_status),
                "dateTime": int(der_status.generator_connect_status_time.timestamp()),
            }

        inverter_status: Optional[dict] = None
        if der_status.inverter_status is not None and der_status.inverter_status_time is not None:
            inverter_status = {
                "value": der_status.inverter_status,
                "dateTime": int(der_status.inverter_status_time.timestamp()),
            }

        lcm_status: Optional[dict] = None
        if der_status.local_control_mode_status is not None and der_status.local_control_mode_status_time is not None:
            lcm_status = {
                "value": der_status.local_control_mode_status,
                "dateTime": int(der_status.local_control_mode_status_time.timestamp()),
            }

        manuf_status: Optional[dict] = None
        if der_status.manufacturer_status is not None and der_status.manufacturer_status_time is not None:
            manuf_status = {
                "value": der_status.manufacturer_status,
                "dateTime": int(der_status.manufacturer_status_time.timestamp()),
            }

        op_mode_status: Optional[dict] = None
        if der_status.operational_mode_status is not None and der_status.operational_mode_status_time is not None:
            op_mode_status = {
                "value": der_status.operational_mode_status,
                "dateTime": int(der_status.operational_mode_status_time.timestamp()),
            }

        soc_status: Optional[dict] = None
        if der_status.state_of_charge_status is not None and der_status.state_of_charge_status_time is not None:
            soc_status = {
                "value": der_status.state_of_charge_status,
                "dateTime": int(der_status.state_of_charge_status_time.timestamp()),
            }

        sm_status: Optional[dict] = None
        if der_status.storage_mode_status is not None and der_status.storage_mode_status_time is not None:
            sm_status = {
                "value": der_status.storage_mode_status,
                "dateTime": int(der_status.storage_mode_status_time.timestamp()),
            }

        stor_conn_status: Optional[dict] = None
        if der_status.storage_connect_status is not None and der_status.storage_connect_status_time is not None:
            stor_conn_status = {
                "value": to_hex_binary(der_status.storage_connect_status),
                "dateTime": int(der_status.storage_connect_status_time.timestamp()),
            }
        return DERStatus.model_validate(
            {
                "href": generate_href(uri.DERStatusUri, rs_params, site_id=site_id, der_id=der_status.site_der_id),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "alarmStatus": (
                    to_hex_binary(int(der_status.alarm_status)) if der_status.alarm_status is not None else None
                ),
                "genConnectStatus": gen_conn_status,
                "inverterStatus": inverter_status,
                "localControlModeStatus": lcm_status,
                "manufacturerStatus": manuf_status,
                "operationalModeStatus": op_mode_status,
                "readingTime": changed_timestamp,
                "stateOfChargeStatus": soc_status,
                "storageModeStatus": sm_status,
                "storConnectStatus": stor_conn_status,
            }
        )

    @staticmethod
    def map_from_request(changed_time: datetime, der_status: DERStatus) -> SiteDERStatus:
        alarm_status: Optional[AlarmStatusType] = None
        if der_status.alarmStatus is not None:
            alarm_status = AlarmStatusType(int(der_status.alarmStatus, 16))

        gen_conn_status: Optional[ConnectStatusType] = None
        gen_conn_status_time: Optional[datetime] = None
        if der_status.genConnectStatus is not None:
            gen_conn_status = ConnectStatusType(int(der_status.genConnectStatus.value, 16))
            gen_conn_status_time = datetime.fromtimestamp(der_status.genConnectStatus.dateTime, timezone.utc)

        stor_conn_status: Optional[ConnectStatusType] = None
        stor_conn_status_time: Optional[datetime] = None
        if der_status.storConnectStatus is not None:
            stor_conn_status = ConnectStatusType(int(der_status.storConnectStatus.value, 16))
            stor_conn_status_time = datetime.fromtimestamp(der_status.storConnectStatus.dateTime, timezone.utc)

        return SiteDERStatus(
            alarm_status=alarm_status,
            generator_connect_status=gen_conn_status,
            generator_connect_status_time=gen_conn_status_time,
            inverter_status=der_status.inverterStatus.value if der_status.inverterStatus else None,
            inverter_status_time=(
                datetime.fromtimestamp(der_status.inverterStatus.dateTime, timezone.utc)
                if der_status.inverterStatus
                else None
            ),
            local_control_mode_status=(
                der_status.localControlModeStatus.value if der_status.localControlModeStatus else None
            ),
            local_control_mode_status_time=(
                datetime.fromtimestamp(der_status.localControlModeStatus.dateTime, timezone.utc)
                if der_status.localControlModeStatus
                else None
            ),
            manufacturer_status=der_status.manufacturerStatus.value if der_status.manufacturerStatus else None,
            manufacturer_status_time=(
                datetime.fromtimestamp(der_status.manufacturerStatus.dateTime, timezone.utc)
                if der_status.manufacturerStatus
                else None
            ),
            operational_mode_status=(
                der_status.operationalModeStatus.value if der_status.operationalModeStatus else None
            ),
            operational_mode_status_time=(
                datetime.fromtimestamp(der_status.operationalModeStatus.dateTime, timezone.utc)
                if der_status.operationalModeStatus
                else None
            ),
            changed_time=changed_time,
            state_of_charge_status=(der_status.stateOfChargeStatus.value if der_status.stateOfChargeStatus else None),
            state_of_charge_status_time=(
                datetime.fromtimestamp(der_status.stateOfChargeStatus.dateTime, timezone.utc)
                if der_status.stateOfChargeStatus
                else None
            ),
            storage_mode_status=(der_status.storageModeStatus.value if der_status.storageModeStatus else None),
            storage_mode_status_time=(
                datetime.fromtimestamp(der_status.storageModeStatus.dateTime, timezone.utc)
                if der_status.storageModeStatus
                else None
            ),
            storage_connect_status=stor_conn_status,
            storage_connect_status_time=stor_conn_status_time,
        )


class DERCapabilityMapper:
    @staticmethod
    def map_to_response(rs_params: RequestStateParameters, site_id: int, der_rating: SiteDERRating) -> DERCapability:
        return DERCapability.model_validate(
            {
                "href": generate_href(uri.DERCapabilityUri, rs_params, site_id=site_id, der_id=der_rating.site_der_id),
                "subscribable": SubscribableType.resource_supports_non_conditional_subscriptions,
                "modesSupported": to_hex_binary(der_rating.modes_supported),
                "rtgAbnormalCategory": der_rating.abnormal_category,
                "rtgMaxA": get_value_multiplier(der_rating.max_a_value, der_rating.max_a_multiplier),
                "rtgMaxAh": get_value_multiplier(der_rating.max_ah_value, der_rating.max_ah_multiplier),
                "rtgMaxChargeRateVA": get_value_multiplier(
                    der_rating.max_charge_rate_va_value, der_rating.max_charge_rate_va_multiplier
                ),
                "rtgMaxChargeRateW": get_value_multiplier(
                    der_rating.max_charge_rate_w_value, der_rating.max_charge_rate_w_multiplier
                ),
                "rtgMaxDischargeRateVA": get_value_multiplier(
                    der_rating.max_discharge_rate_va_value, der_rating.max_discharge_rate_va_multiplier
                ),
                "rtgMaxDischargeRateW": get_value_multiplier(
                    der_rating.max_discharge_rate_w_value, der_rating.max_discharge_rate_w_multiplier
                ),
                "rtgMaxV": get_value_multiplier(der_rating.max_v_value, der_rating.max_v_multiplier),
                "rtgMaxVA": get_value_multiplier(der_rating.max_va_value, der_rating.max_va_multiplier),
                "rtgMaxVar": get_value_multiplier(der_rating.max_var_value, der_rating.max_var_multiplier),
                "rtgMaxVarNeg": get_value_multiplier(der_rating.max_var_neg_value, der_rating.max_var_neg_multiplier),
                "rtgMaxW": get_value_multiplier(der_rating.max_w_value, der_rating.max_w_multiplier),
                "rtgMaxWh": get_value_multiplier(der_rating.max_wh_value, der_rating.max_wh_multiplier),
                "rtgMinPFOverExcited": get_value_multiplier(
                    der_rating.min_pf_over_excited_displacement,
                    der_rating.min_pf_over_excited_multiplier,
                    value_name="displacement",
                ),
                "rtgMinPFUnderExcited": get_value_multiplier(
                    der_rating.min_pf_under_excited_displacement,
                    der_rating.min_pf_under_excited_multiplier,
                    value_name="displacement",
                ),
                "rtgMinV": get_value_multiplier(der_rating.min_v_value, der_rating.min_v_multiplier),
                "rtgNormalCategory": der_rating.normal_category,
                "rtgOverExcitedPF": get_value_multiplier(
                    der_rating.over_excited_pf_displacement,
                    der_rating.over_excited_pf_multiplier,
                    value_name="displacement",
                ),
                "rtgOverExcitedW": get_value_multiplier(
                    der_rating.over_excited_w_value, der_rating.over_excited_pf_multiplier
                ),
                "rtgReactiveSusceptance": get_value_multiplier(
                    der_rating.reactive_susceptance_value, der_rating.reactive_susceptance_multiplier
                ),
                "rtgUnderExcitedPF": get_value_multiplier(
                    der_rating.under_excited_pf_displacement,
                    der_rating.under_excited_pf_multiplier,
                    value_name="displacement",
                ),
                "rtgUnderExcitedW": get_value_multiplier(
                    der_rating.under_excited_w_value, der_rating.under_excited_w_multiplier
                ),
                "rtgVNom": get_value_multiplier(der_rating.v_nom_value, der_rating.v_nom_multiplier),
                "type_": der_rating.der_type,
                "doeModesSupported": der_rating.doe_modes_supported,
            }
        )

    @staticmethod
    def map_from_request(changed_time: datetime, der_cap: DERCapability) -> SiteDERRating:

        m = SiteDERRating(
            modes_supported=DERControlType(int(der_cap.modesSupported, 16)),
            der_type=der_cap.type_,
            doe_modes_supported=der_cap.doeModesSupported,
            changed_time=changed_time,
            normal_category=der_cap.rtgNormalCategory,
            abnormal_category=der_cap.rtgAbnormalCategory,
        )
        (m.max_a_value, m.max_a_multiplier) = set_value_multiplier(der_cap.rtgMaxA)
        (m.max_ah_value, m.max_ah_multiplier) = set_value_multiplier(der_cap.rtgMaxAh)
        (m.max_charge_rate_va_value, m.max_charge_rate_va_multiplier) = set_value_multiplier(der_cap.rtgMaxChargeRateVA)
        (m.max_charge_rate_w_value, m.max_charge_rate_w_multiplier) = set_value_multiplier(der_cap.rtgMaxChargeRateW)
        (m.max_discharge_rate_va_value, m.max_discharge_rate_va_multiplier) = set_value_multiplier(
            der_cap.rtgMaxDischargeRateVA
        )
        (m.max_discharge_rate_w_value, m.max_discharge_rate_w_multiplier) = set_value_multiplier(
            der_cap.rtgMaxDischargeRateW
        )
        (m.max_v_value, m.max_v_multiplier) = set_value_multiplier(der_cap.rtgMaxV)
        (m.max_va_value, m.max_va_multiplier) = set_value_multiplier(der_cap.rtgMaxVA)
        (m.max_var_value, m.max_var_multiplier) = set_value_multiplier(der_cap.rtgMaxVar)
        (m.max_var_neg_value, m.max_var_neg_multiplier) = set_value_multiplier(der_cap.rtgMaxVarNeg)
        (m.max_w_value, m.max_w_multiplier) = cast(tuple[int, int], set_value_multiplier(der_cap.rtgMaxW))
        (m.max_wh_value, m.max_wh_multiplier) = set_value_multiplier(der_cap.rtgMaxWh)

        (m.min_pf_over_excited_displacement, m.min_pf_over_excited_multiplier) = set_value_multiplier(
            der_cap.rtgMinPFOverExcited
        )
        (m.min_pf_under_excited_displacement, m.min_pf_under_excited_multiplier) = set_value_multiplier(
            der_cap.rtgMinPFUnderExcited
        )
        (m.min_v_value, m.min_v_multiplier) = set_value_multiplier(der_cap.rtgMinV)
        (m.over_excited_pf_displacement, m.over_excited_pf_multiplier) = set_value_multiplier(der_cap.rtgOverExcitedPF)
        (m.over_excited_w_value, m.over_excited_w_multiplier) = set_value_multiplier(der_cap.rtgOverExcitedW)
        (m.reactive_susceptance_value, m.reactive_susceptance_multiplier) = set_value_multiplier(
            der_cap.rtgReactiveSusceptance
        )
        (m.under_excited_pf_displacement, m.under_excited_pf_multiplier) = set_value_multiplier(
            der_cap.rtgUnderExcitedPF
        )
        (m.under_excited_w_value, m.under_excited_w_multiplier) = set_value_multiplier(der_cap.rtgUnderExcitedW)
        (m.v_nom_value, m.v_nom_multiplier) = set_value_multiplier(der_cap.rtgVNom)

        return m
