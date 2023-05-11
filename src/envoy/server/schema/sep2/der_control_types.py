from pydantic_xml import element

from envoy.server.schema.sep2 import types
from envoy.server.schema.sep2.base import BaseXmlModelWithNS


class FixedVar(BaseXmlModelWithNS):
    """Specifies a signed setpoint for reactive power."""

    refType: types.DERUnitRefType = element()  # Signed setpoint for reactive power
    value: types.SignedPerCent = element()  # Specify a signed setpoint for reactive power in %


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
