import os
from typing import Callable, List
from xml.etree import ElementTree as ET

import pytest
from defusedxml import ElementTree

from tests.data.sep2_xml.xml_to_model_mappings import MAPPINGS

# assumes files for testing are in same dir as test
INPUT_DIR = os.path.dirname(__file__)


class AssertionResponse:
    def __init__(self, input_type, value: bool, exceptions: List[str]) -> None:
        self.input_type = input_type
        self.value = value
        self.exceptions = exceptions


def comparison_func(obj1: ET.Element, obj2: ET.Element, assertions: List[Callable]) -> AssertionResponse:
    """_summary_ TODO
    """

    if not obj1.tag == obj2.tag:
        raise ValueError(f"{obj1} and {obj2} must have the same tags!")

    exc = []
    for func in assertions:
        if func(obj1, obj2) is not True:
            exc.append(func.__name__)

    val = False if len(exc) > 0 else True
    return AssertionResponse(input_type=obj1.tag, value=val, exceptions=exc)


@pytest.mark.parametrize("file_name, xml_type, assertions_list", MAPPINGS)
def test_xml_round_trip(file_name: str, xml_type: str, assertions_list: List[Callable]) -> None:
    """Assert that we are able to round-trip examples from the 2030.5 spec document.
    Specifically, that we can instantiate an xml_type instance from that example, and
    that the XML generated from that instance passes some comparison_func metric against
    the example"""

    file_loc = os.path.join(INPUT_DIR, file_name)
    buff = open(file_loc).read()

    # parse the input buffer to ElementTree.Element
    input_as_XML = ElementTree.fromstring(buff)

    # create an instance of xml_type, then convert to an ElementTree.Element
    schema_instance = xml_type.from_xml(buff)
    instance_as_bytes = schema_instance.to_xml(skip_empty=True)
    output_as_XML = ElementTree.fromstring(instance_as_bytes)

    comp: AssertionResponse
    comp = comparison_func(input_as_XML, output_as_XML, assertions_list)

    assert comp.value, (comp.input_type, comp.exceptions)
