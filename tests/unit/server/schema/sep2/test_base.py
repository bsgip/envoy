
from envoy.server.schema.sep2.base import IdentifiedObject
from envoy.server.schema.sep2.end_device import AbstractDevice
from envoy.server.schema.sep2.metering import TOUType
from envoy.server.schema.sep2.pricing import RateComponentResponse, RoleFlagsType, TimeTariffIntervalResponse
from tests.data.fake.generator import generate_class_instance


def test_roundtrip_identified_object():
    """Test to test a detected issue with mrid encoding"""
    initial: IdentifiedObject = generate_class_instance(IdentifiedObject)
    output: IdentifiedObject = IdentifiedObject.from_xml(initial.to_xml())

    assert initial.mRID == output.mRID
    assert initial.description == output.description
    assert initial.version == output.version


def test_roundtrip_abstract_device():
    """Test to test a detected issue with mrid encoding"""
    initial: AbstractDevice = generate_class_instance(AbstractDevice)
    output: AbstractDevice = AbstractDevice.from_xml(initial.to_xml())

    assert initial.deviceCategory == output.deviceCategory
    assert initial.lFDI == output.lFDI
    assert initial.sFDI == output.sFDI
