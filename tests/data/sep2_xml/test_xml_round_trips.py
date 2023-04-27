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


def comparison_func(ref: ET.Element, model: ET.Element, assertions: List[Callable]) -> AssertionResponse:
    """Generic comparison function, which takes both a reference ET.Element and the
    model ET.Element which we wish to compare against the reference, and a list of
    assertions which should return True (and any optional extra return values) if
    the assertions are True, or False (and any optional extra return values) if the
    assertions are not True.

    Returns an AssertionResponse which stores the name of the object against which
    comparison is being tested, and additionally stores True if all assertion funcs
    in the assertion list return True, else stores False alongside all the assertions
    and the extra information returned by each for each assertion which did not return True.

    Returns ValueError if called on a ref and model possessing different top-level tags.
    """

    if not ref.tag == model.tag:
        raise ValueError(f"{ref} and {model} must have the same tags!")

    exc = []
    for func in assertions:
        ret_val, *extra = func(ref, model)
        if ret_val is not True:
            exc.append((func.__name__, extra))

    val = False if len(exc) > 0 else True
    return AssertionResponse(input_type=ref.tag, value=val, exceptions=exc)


@pytest.mark.parametrize("file_name, xml_type, assertions_list", MAPPINGS)
def test_xml_round_trip(file_name: str, xml_type: str, assertions_list: List[Callable]) -> None:
    """Assert that we are able to round-trip examples from the 2030.5 spec document.
    Specifically, that we can instantiate an xml_type instance from that example, and
    that the XML generated from that instance passes some comparison_func metric against
    the example"""

    file_loc = os.path.join(INPUT_DIR, file_name)
    buff = open(file_loc).read()

    # parse the input buffer to ElementTree.Element
    ref_as_XML = ElementTree.fromstring(buff)

    # create an instance of xml_type, then convert to an ElementTree.Element
    schema_instance = xml_type.from_xml(buff)
    instance_as_bytes = schema_instance.to_xml(skip_empty=True)
    model_as_XML = ElementTree.fromstring(instance_as_bytes)

    comp: AssertionResponse
    comp = comparison_func(ref_as_XML, model_as_XML, assertions_list)

    assert comp.value, (comp.input_type, comp.exceptions)
