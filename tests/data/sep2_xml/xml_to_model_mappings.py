"""
MAPPINGS are used when traversing round-trips in test_xml_round_trip. Each element of
MAPPING is a tuple containing a file name in tests/data/sep2_xml, the corresponding
Pydantic-XML schema, and a list of Callables which should accept both the input XML
model parsed from the given file name, and the output XML model (ElementTree.Element's),
and return True if the comparison conditions implied by that Callable are passed.
"""

from typing import List, Tuple
from xml.etree import ElementTree as ET

from envoy.server.schema.sep2.device_capability import DeviceCapabilityResponse
from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceResponse
from envoy.server.schema.sep2.metering import ReadingType
from envoy.server.schema.sep2.pricing import (
    ConsumptionTariffIntervalListResponse,
    RateComponentListResponse,
    TariffProfileResponse,
)


def compare_ET_Element_to_reference_ET_Element(
    ref: ET.Element, model: ET.Element, xml_type: str, allowed_missing: list[str], strict: bool
) -> Tuple[bool, List[str]]:
    """Compare an ElementTree.Element object against some reference object of the
    same type. We expect each element in ref to exist in model. The model is considered
    equivalent to ref iff:
    (a) the tags of the parent elements match exactly,
    (b) the attrib of the parent elements match exactly
    (c) the text of the parent elements match exactly (after stripping)
    (d) each child Element in the ref is present in the model
        (where present is defined by possessing matching tags), and
    (e) for each child Element in the ref, the child attributes and their values
        match the attributes and the values of the model exactly.
    """

    error_messages = []

    if model.tag != ref.tag:
        error_messages.append(f"Input tag ({model.tag}) does not match reference tag ({ref.tag})")

    for k, v in ref.attrib.items():
        match = model.get(k, None)

        if not match:
            if strict and k not in allowed_missing:
                error_messages.append(f"Missing key ({k}) in input attrib ({model.attrib})")

        elif v != match:
            error_messages.append(
                f"Key ({k}) in input attrib ({model.attrib}) does not match ref attrib ({ref.attrib})"
            )

    # reference inputs have trailing whitespace when read from buffer
    # there's no 'right' way to deal with this in the absence of an XML schema
    model_text = model.text.strip() if model.text is not None else ""
    ref_text = ref.text.strip() if ref.text is not None else ""

    if model_text != ref_text:
        error_messages.append(f"Input text ({model.text}) does not match reference text ({ref.text})")

    # check if each element in the reference is present in the input model
    for c in ref:
        matches = [m for m in model if m.tag == c.tag]
        required = xml_type.schema().get("required", [])

        # Two conditions to consider, if there are no matches:
        # 1. Strict and tag is required and we haven't allowed it to be missing: error
        # 2. Strict and tag is not required and we haven't allowed it to be missing: error

        if not matches:
            if strict and c.tag in required and c.tag not in allowed_missing:
                error_messages.append(f"No matching required child for {c.tag} in reference (tag required).")

            elif strict and c.tag not in required and c.tag not in allowed_missing:
                error_messages.append(f"No matching optional child for {c.tag} in reference.")

        else:
            result, child_errors = compare_ET_Element_to_reference_ET_Element(
                c, matches[0], xml_type, allowed_missing, strict
            )
            if not result:
                error_messages.append(f"Child element ({c.tag}) failed comparison: {child_errors}")

    if error_messages:
        return False, error_messages
    else:
        return True, []


enddevicelist_assertions = [compare_ET_Element_to_reference_ET_Element]
enddevice_assertions = [compare_ET_Element_to_reference_ET_Element]
devicecapability_assertions = [compare_ET_Element_to_reference_ET_Element]
readingtype_assertions = [compare_ET_Element_to_reference_ET_Element]
consumptiontariffintervallist_assertions = [compare_ET_Element_to_reference_ET_Element]
ratecomponentlist_assertions = [compare_ET_Element_to_reference_ET_Element]
tariffprofile_assertions = [compare_ET_Element_to_reference_ET_Element]
timetariffintervallist_assertions = [compare_ET_Element_to_reference_ET_Element]

MAPPINGS = [
    (
        "device_capability/devicecapability.xml",
        DeviceCapabilityResponse,
        devicecapability_assertions,
        ["{urn:ieee:std:2030.5:ns}SelfDeviceLink"],
        True,
    ),
    # ("does/dercontrollist.xml", ..., ...),
    # ("does/derprogramlist.xml", ..., ...),
    (
        "end_device_resource/enddevicelist.xml",
        EndDeviceListResponse,
        enddevicelist_assertions,
        ["{urn:ieee:std:2030.5:ns}ConfigurationLink"],
        True,
    ),
    (
        "end_device_resource/enddevice.xml",
        EndDeviceResponse,
        enddevice_assertions,
        ["{urn:ieee:std:2030.5:ns}ConfigurationLink"],
        True,
    ),
    # ("end_device_resource/functionsetassignmentslist.xml", ..., ...),
    # ("end_device_resource/registration.xml", ..., ...),
    # ("meter_mirroring/meterreadinglist.xml", ..., ...),
    # ("meter_mirroring/readinglist.xml", ..., ...),
    # ("meter_mirroring/readingsetlist.xml, ..., ..."),
    ("meter_mirroring/readingtype.xml", ReadingType, readingtype_assertions, [], True),
    # ("meter_mirroring/usagepointlist.xml, ..., ..."),
    (
        "pricing/consumptiontariffintervallist.xml",
        ConsumptionTariffIntervalListResponse,
        consumptiontariffintervallist_assertions,
        [],
        True,
    ),
    ("pricing/ratecomponentlist.xml", RateComponentListResponse, ratecomponentlist_assertions, [], True),
    ("pricing/readingtype.xml", ReadingType, readingtype_assertions, [], True),
    (
        "pricing/tariffprofile.xml",
        TariffProfileResponse,
        tariffprofile_assertions,
        ["{urn:ieee:std:2030.5:ns}primacy"],
        True,
    ),
    # (
    #     "pricing/timetariffintervallist.xml",
    #     TimeTariffIntervalListResponse,
    #     timetariffintervallist_assertions,
    #     ["subscribable", "{urn:ieee:std:2030.5:ns}EventStatus"],
    #     True,
    # ),
]
