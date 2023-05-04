from typing import Optional

from pydantic_xml import element

from envoy.server.schema.sep2 import base


# The SEP2 standard doesn't explicitly state that FunctionSetAssignments derives from
# IdentifiedObject nor SubscribableResource. However the fields present on FunctionSetAssignments
# matches those present in IdentifiedObject and SubscribableResource so we have decided to inherit from these
# in addition to explicitly stated parent class, namely, FunctionSetAssignmentsBase
class FunctionSetAssignmentsResponse(
    base.FunctionSetAssignmentsBase, base.IdentifiedObject, base.SubscribableResource, tag="FunctionSetAssignments"
):
    pass


class FunctionSetAssignmentsListResponse(base.SubscribableList, tag="FunctionSetAssignments"):
    pollrate: base.PollRateType = base.DEFAULT_POLLRATE

    FunctionSetAssignments: Optional[list[FunctionSetAssignmentsResponse]] = element()
