"""
MAPPINGS are used when traversing round-trips in test_xml_round_trip. Each element of
MAPPING is a tuple containing a file name in tests/data/sep2_xml, the corresponding
Pydantic-XML schema, and a list of Callables which should accept both the input XML
model parsed from the given file name, and the output XML model (ElementTree.Element's),
and return True if the comparison conditions implied by that Callable are passed.
"""

from typing import List, Tuple
from xml.etree import ElementTree as ET

from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceResponse


# example comparison function
def compare_ET_Element_to_reference_ET_Element(ref: ET.Element, model: ET.Element) -> Tuple[bool, List[str]]:
    """Compare an ElementTree.Element object against some reference object of the
    same type. We expect each element in ref to exist in model. The model is considered
    equivalent to ref iff:
    (a) the tags of the parent elements match exactly,
    (b) the attrib of the parent elements match exactly
    (c) each child Element in the ref is present in the model
        (where present is defined by possessing matching tags), and
    (d) for each child Element in the ref, the child attributes and their values
        match the attributes and the values of the model exactly.
    """

    error_messages = []

    if model.tag != ref.tag:
        error_messages.append(f"Input tag ({model.tag}) does not match reference tag ({ref.tag})")

    # a weaker assertion would be to check each item in the attrib dict for equality
    if model.attrib != ref.attrib:
        error_messages.append(f"Input attrib ({model.attrib}) does not match reference attrib ({ref.attrib})")

    # check if each element in the reference is present in the input model
    for child in ref:
        matches = [m for m in model if m.tag == child.tag]
        if len(matches) != 1:
            error_messages.append(f"Could not find matching child element for {child.tag} in reference.")

        else:
            result, child_errors = compare_ET_Element_to_reference_ET_Element(child, matches[0])
            if not result:
                error_messages.append(f"Child element ({child.tag}) failed comparison: {child_errors}")

    if error_messages:
        return False, error_messages
    else:
        return True, []


# example list of assertions for EndDeviceListResponse instances
enddevicelist_assertions = [
    compare_ET_Element_to_reference_ET_Element,
]

enddevice_assertions = [
    compare_ET_Element_to_reference_ET_Element,
]

MAPPINGS = [
    # ("device_capability/devicecapability.xml", ..., ...),
    # ("does/dercontrollist.xml", ..., ...),
    # ("does/derprogramlist.xml", ..., ...),
    ("end_device_resource/enddevicelist.xml", EndDeviceListResponse, enddevicelist_assertions),
    ("end_device_resource/enddevice.xml", EndDeviceResponse, enddevice_assertions),
    # ("end_device_resource/functionsetassignmentslist.xml", ..., ...),
    # ("end_device_resource/registration.xml", ..., ...),
    # ("meter_mirroring/meterreadinglist.xml", ..., ...),
    # ("meter_mirroring/readinglist.xml", ..., ...),
    # ("meter_mirroring/readingsetlist.xml, ..., ..."),
    # ("meter_mirroring/readingtype.xml, ..., ..."),
    # ("meter_mirroring/usagepointlist.xml, ..., ..."),
    # ("pricing/consumptiontariffintervallist.xml, ..., ..."),
    # ("pricing/ratecomponentlist.xml, ..., ..."),
    # ("pricing/readingtype.xml, ..., ..."),
    # ("pricing/tariffprofile.xml, ..., ..."),
    # ("pricing/timetariffintervallist.xml, ..., ..."),
]
