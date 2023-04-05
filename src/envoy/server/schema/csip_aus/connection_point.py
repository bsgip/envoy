

from pydantic_xml import element

from envoy.server.schema.sep2.base import BaseXmlModelWithNS, Link


class ConnectionPointLink(Link, ns="csipaus"):
    pass


class ConnectionPoint(BaseXmlModelWithNS, tag="ConnectionPoint", ns="csipaus"):
    """Contains identification information related to the network location at which the EndDevice is installed."""
    id: str = element()  # Typically used as the NMI
