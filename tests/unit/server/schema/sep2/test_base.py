from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.der import DERControlBase, DERControlResponse
from envoy_schema.server.schema.sep2.end_device import AbstractDevice
from envoy_schema.server.schema.sep2.identification import IdentifiedObject
from envoy_schema.server.schema.sep2.types import DateTimeIntervalType, SubscribableType


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


def test_roundtrip_csip_aus_der_control():
    """Validates the DERControlREsponse roundtrip in response to some discovered errors"""
    initial: DERControlResponse = generate_class_instance(DERControlResponse)
    initial.subscribable = SubscribableType.resource_does_not_support_subscriptions
    initial.interval = DateTimeIntervalType.model_validate({"duration": 111, "start": 222})
    initial.DERControlBase_ = DERControlBase.model_validate(
        {
            "opModImpLimW": {"value": 9988, "multiplier": 1},
            "opModExpLimW": {"value": 7766, "multiplier": 10},
            "opModGenLimW": {"value": 5544, "multiplier": 100},
            "opModLoadLimW": {"value": 3322, "multiplier": 1000},
        }
    )
    xml = initial.to_xml(skip_empty=True)
    assert "9988" in xml.decode()
    assert "7766" in xml.decode()
    assert "5544" in xml.decode()
    assert "3322" in xml.decode()
    output: DERControlResponse = DERControlResponse.from_xml(xml)
    assert output.DERControlBase_
    assert output.DERControlBase_.opModImpLimW.value == 9988
    assert output.DERControlBase_.opModExpLimW.value == 7766
    assert output.DERControlBase_.opModGenLimW.value == 5544
    assert output.DERControlBase_.opModLoadLimW.value == 3322
