

from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2.base import BaseXmlModelWithNS, Link


class ConnectionPointLink(Link, ns="csipaus"):
    pass


class ConnectionPointRequest(BaseXmlModelWithNS, tag="ConnectionPoint", ns="csipaus"):
    """Contains identification information related to the network location at which the EndDevice is installed."""
    id: Optional[str] = element(default=None)  # Typically used as the NMI


class ConnectionPointResponse(BaseXmlModelWithNS, tag="ConnectionPoint", ns="csipaus"):
    """Contains identification information related to the network location at which the EndDevice is installed."""
    id: Optional[str] = element()  # Typically used as the NMI
