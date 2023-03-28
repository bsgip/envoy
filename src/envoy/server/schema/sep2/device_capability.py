from typing import Literal

import pydantic_xml

from envoy.server.schema.sep2.base import Resource


class DeviceCapabilityResponse(Resource):
    href: Literal["/dcap"] = pydantic_xml.attr()
