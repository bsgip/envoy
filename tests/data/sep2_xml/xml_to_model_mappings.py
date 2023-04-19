"""
MAPPINGS are used when traversing round-trips in test_xml_round_trip. Each element of
MAPPING is a tuple containing a file name in tests/data/sep2_xml, the corresponding
Pydantic-XML schema, and a list of Callables which should accept both the input XML
model parsed from the given file name, and the output XML model (ElementTree.Element's),
and return True if the comparison conditions implied by that Callable are passed.
"""

from xml.etree import ElementTree as ET

from envoy.server.schema.sep2.end_device import EndDeviceListResponse, EndDeviceResponse


# example comparison function
def func1(x: ET.Element, y: ET.Element):
    return True


# example list of assertions for EndDeviceListResponse instances
enddevicelist_assertions = [
    func1,
]

enddevice_assertions = [
    func1,
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
