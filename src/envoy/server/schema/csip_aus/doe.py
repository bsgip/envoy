from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.der import ActivePower, DERControlBase


class CSIPAusDERControlBase(DERControlBase, tag="DERControlBase"):
    """Contains identification information related to the network location at which the EndDevice is installed."""
    opModImpLimW: Optional[ActivePower] = element(ns="csipaus")  # constraint on the imported AP at the connection point
    opModExpLimW: Optional[ActivePower] = element(ns="csipaus")  # constraint on the exported AP at the connection point
    opModGenLimW: Optional[ActivePower] = element(ns="csipaus")  # max limit on discharge watts for a single DER
    opModLoadLimW: Optional[ActivePower] = element(ns="csipaus")  # max limit on charge watts for a single DER
