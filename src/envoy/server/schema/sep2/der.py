from enum import IntEnum
from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.base import BaseXmlModelWithNS, HexBinary32, IdentifiedObject, Link
from envoy.server.schema.sep2.base import List as Sep2List
from envoy.server.schema.sep2.base import ListLink, SubscribableIdentifiedObject, SubscribableList
from envoy.server.schema.sep2.end_device import DeviceCategory
from envoy.server.schema.sep2.event import RandomizableEvent
from envoy.server.schema.sep2.pricing import PrimacyType


class SignedPerCent(int):
    # Used for signed percentages, specified in hundredths of a percent, -10000 - 10000. (10000 = 100%)
    pass


class PerCent(int):
    # Used for percentages, specified in hundredths of a percent, 0 - 10000. (10000 = 100%)
    pass


class DERUnitRefType(IntEnum):
    """Specifies context for interpreting percent values:. All other values are reserved"""

    NOT_APPLICABLE = 0
    PERC_SET_MAX_W = 1
    PERC_SET_MAX_VAR = 2
    PERC_STAT_VAR_AVAIL = 3
    PERC_SET_EFFECTIVE_V = 4
    PERC_SET_MAX_CHARGE_RATE_W = 5
    PERC_SET_MAX_DISCHARGE_RATE_W = 6
    PERC_STAT_W_AVAIL = 7


class FixedVar(BaseXmlModelWithNS):
    """Specifies a signed setpoint for reactive power."""

    refType: DERUnitRefType = element()  # Signed setpoint for reactive power
    value: SignedPerCent = element()  # Specify a signed setpoint for reactive power in %


class PowerFactorWithExcitation(BaseXmlModelWithNS):
    """Specifies a setpoint for Displacement Power Factor, the ratio between apparent and active powers at the
    fundamental frequency (e.g. 60 Hz) and includes an excitation flag."""

    displacement: int = element()  # Significand of an unsigned value of cos(theta) between 0 and 1.0.
    excitation: bool = element()  # True = DER absorbing, False = DER injecting reactive power
    multiplier: int = element()  # Specifies exponent of 'displacement'.


class ReactivePower(BaseXmlModelWithNS):
    """The reactive power Q"""

    value: int = element()  # Value in volt-amperes reactive (var) (uom 63)
    multiplier: int = element()  # Specifies exponent of 'value'.


class ActivePower(BaseXmlModelWithNS):
    """The active/real power P"""

    value: int = element()  # Value in volt-amperes reactive (var) (uom 63)
    multiplier: int = element()  # Specifies exponent of 'value'.


class DERControlBase(BaseXmlModelWithNS):
    """Distributed Energy Resource (DER) control values."""

    opModConnect: Optional[bool] = element()  # Set DER as connected (true) or disconnected (false).
    opModEnergize: Optional[bool] = element()  # Set DER as energized (true) or de-energized (false).
    opModFixedPFAbsorbW: Optional[PowerFactorWithExcitation] = element()  # requested PF when AP is being absorbed
    opModFixedPFInjectW: Optional[PowerFactorWithExcitation] = element()  # requested PF when AP is being injected
    opModFixedVar: Optional[FixedVar] = element()  # specifies the delivered or received RP setpoint.
    opModFixedW: Optional[SignedPerCent] = element()  # specifies a requested charge/discharge mode setpoint
    opModFreqDroop: Optional[int] = element()  # Specifies a frequency-watt operation
    opModFreqWatt: Optional[Link] = element()  # Specify DERCurveLink for curveType == 0
    opModHFRTMayTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 1
    opModHFRTMustTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 2
    opModHVRTMayTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 3
    opModHVRTMomentaryCessation: Optional[Link] = element()  # Specify DERCurveLink for curveType == 4
    opModHVRTMustTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 5
    opModLFRTMayTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 6
    opModLFRTMustTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 7
    opModLVRTMayTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 8
    opModLVRTMomentaryCessation: Optional[Link] = element()  # Specify DERCurveLink for curveType == 9
    opModLVRTMustTrip: Optional[Link] = element()  # Specify DERCurveLink for curveType == 10
    opModMaxLimW: Optional[PerCent] = element()  # maximum active power generation level at electrical coupling point
    opModTargetVar: Optional[ReactivePower] = element()  # Target reactive power, in var
    opModTargetW: Optional[ActivePower] = element()  # Target active power, in Watts
    opModVoltVar: Optional[Link] = element()  # Specify DERCurveLink for curveType == 11
    opModVoltWatt: Optional[Link] = element()  # Specify DERCurveLink for curveType == 12
    opModWattPF: Optional[Link] = element()  # Specify DERCurveLink for curveType == 13
    opModWattVar: Optional[Link] = element()  # Specify DERCurveLink for curveType == 14
    rampTms: Optional[int] = element()  # Requested ramp time, in hundredths of a second

    # CSIP Aus Extensions (encoded here as it makes decoding a whole lot simpler)
    opModImpLimW: Optional[ActivePower] = element(ns="csipaus")  # constraint on the imported AP at the connection point
    opModExpLimW: Optional[ActivePower] = element(ns="csipaus")  # constraint on the exported AP at the connection point
    opModGenLimW: Optional[ActivePower] = element(ns="csipaus")  # max limit on discharge watts for a single DER
    opModLoadLimW: Optional[ActivePower] = element(ns="csipaus")  # max limit on charge watts for a single DER


class DefaultDERControl(SubscribableIdentifiedObject):
    """Contains control mode information to be used if no active DERControl is found."""

    setESDelay: Optional[int] = element()  # Enter service delay, in hundredths of a second.
    setESHighFreq: Optional[int] = element()  # Enter service frequency high. Specified in hundredths of Hz
    setESHighVolt: Optional[int] = element()  # Enter service voltage high. Specified as an effective percent voltage,
    setESLowFreq: Optional[int] = element()  # Enter service frequency low. Specified in hundredths of Hz
    setESLowVolt: Optional[int] = element()  # Enter service voltage low. Specified as an effective percent voltage,
    setESRampTms: Optional[int] = element()  # Enter service ramp time, in hundredths of a second
    setESRandomDelay: Optional[int] = element()  # Enter service randomized delay, in hundredths of a second.
    setGradW: Optional[int] = element()  # Set default rate of change (ramp rate) of active power output
    setSoftGradW: Optional[int] = element()  # Set soft-start rate of change (soft-start ramp rate) of AP output
    DERControlBase_: DERControlBase = element(tag="DERControlBase")


class DERControlResponse(RandomizableEvent, tag="DERControl"):
    """Distributed Energy Resource (DER) time/event-based control."""

    deviceCategory: Optional[HexBinary32] = element()  # the bitmap indicating device categories that SHOULD respond.
    DERControlBase_: DERControlBase = element(tag="DERControlBase")


class DERControlListResponse(SubscribableList, tag="DERControlList"):
    DERControl: Optional[list[DERControlResponse]] = element()


class DERProgramResponse(SubscribableIdentifiedObject, tag="DERProgram"):
    """sep2 DERProgram"""

    primacy: PrimacyType = element()
    DefaultDERControlLink: Optional[Link] = element()
    ActiveDERControlListLink: Optional[ListLink] = element()
    DERControlListLink: Optional[ListLink] = element()
    DERCurveListLink: Optional[ListLink] = element()


class DERProgramListResponse(SubscribableList, tag="DERProgramList"):
    DERProgram: list[DERProgramResponse] = element()
    pollRate: Optional[int] = element()  # The default polling rate for this resource and all resources below in seconds


class DemandResponseProgramResponse(IdentifiedObject, tag="DemandResponseProgram"):
    """sep2 Demand response program"""

    availabilityUpdatePercentChangeThreshold: Optional[PerCent] = element()
    availabilityUpdatePowerChangeThreshold: Optional[ActivePower] = element()
    primacy: PrimacyType = element()
    ActiveEndDeviceControlListLink: Optional[ListLink] = element()
    EndDeviceControlListLink: Optional[ListLink] = element()


class DemandResponseProgramListResponse(Sep2List, tag="DemandResponseProgramList"):
    DemandResponseProgram: Optional[list[DemandResponseProgramResponse]] = element()


class EndDeviceControlResponse(RandomizableEvent, tag="EndDeviceControl"):
    """Instructs an EndDevice to perform a specified action."""

    deviceCategory: DeviceCategory = element()
    drProgramMandatory: bool = element()
    loadShiftForward: bool = element()
    overrideDuration: Optional[int] = element()
