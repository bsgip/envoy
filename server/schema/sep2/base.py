from typing import Optional

from pydantic_xml import BaseXmlModel, attr

""" Abstract
"""
nsmap = {"": "urn:ieee:std:2030.5:ns"}


class BaseXmlModelWithNS(BaseXmlModel, nsmap=nsmap):
    pass


""" Resource
"""


class PollRateType(BaseXmlModelWithNS):
    pollRate: Optional[int] = attr()


class Resource(BaseXmlModelWithNS):
    pass


class PENType(int):
    pass


class VersionType(int):
    pass


class mRIDType(int):
    pass


class IdentifiedObject(Resource):
    description: Optional[str]
    mRID: mRIDType
    version: Optional[VersionType]
