from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2 import types
from envoy.server.schema.sep2.identification import (
    IdentifiedObject,
    Link,
    ListLink,
    Resource,
    SubscribableList,
    SubscribableResource,
)


class FunctionSetAssignmentsBase(Resource):
    # Optional (0..1) Links
    TimeLink: Optional[Link] = element()

    # Optional (0..1) ListLinks
    CustomerAccountListLink: Optional[ListLink] = element()
    DemandResponseProgramListLink: Optional[ListLink] = element()
    DERProgramListLink: Optional[ListLink] = element()
    FileListLink: Optional[ListLink] = element()
    MessagingProgramListLink: Optional[ListLink] = element()
    PrepaymentListLink: Optional[ListLink] = element()
    ResponseSetListLink: Optional[ListLink] = element()
    TariffProfileListLink: Optional[ListLink] = element()
    UsagePointListLink: Optional[ListLink] = element()


# The SEP2 standard doesn't explicitly state that FunctionSetAssignments derives from
# IdentifiedObject nor SubscribableResource. However the fields present on FunctionSetAssignments
# matches those present in IdentifiedObject and SubscribableResource so we have decided to inherit from these
# in addition to explicitly stated parent class, namely, FunctionSetAssignmentsBase
class FunctionSetAssignmentsResponse(
    FunctionSetAssignmentsBase, IdentifiedObject, SubscribableResource, tag="FunctionSetAssignments"
):
    pass


class FunctionSetAssignmentsListResponse(SubscribableList, tag="FunctionSetAssignments"):
    pollrate: types.PollRateType = types.DEFAULT_POLLRATE

    FunctionSetAssignments: Optional[list[FunctionSetAssignmentsResponse]] = element()
