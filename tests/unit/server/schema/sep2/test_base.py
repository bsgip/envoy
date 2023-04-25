
from envoy.server.schema.csip_aus.doe import CSIPAusDERControlBase
from envoy.server.schema.sep2.base import IdentifiedObject
from envoy.server.schema.sep2.der import ActivePower, DERControlBase, DERControlResponse
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


def test_roundtrip_csip_aus_der_control():
    initial: DERControlResponse = generate_class_instance(DERControlResponse)
    opModImpLimW = ActivePower.validate({"value": 9988, "multiplier": 1})
    opModExpLimW = ActivePower.validate({"value": 7766, "multiplier": 10})
    opModGenLimW = ActivePower.validate({"value": 5544, "multiplier": 100})
    opModLoadLimW = ActivePower.validate({"value": 3322, "multiplier": 1000})
    initial.DERControlBase_ = DERControlBase.validate({
        "opModImpLimW": opModImpLimW,
        "opModExpLimW": opModExpLimW,
        "opModGenLimW": opModGenLimW,
        "opModLoadLimW": opModLoadLimW,
    })
    ap = opModExpLimW.to_xml()
    ap2 = initial.DERControlBase_.to_xml()

    # xml = initial.to_xml()
    # assert str(opModImpLimW.value) in xml
    # assert str(opModExpLimW.value) in xml
    # assert str(opModGenLimW.value) in xml
    # assert str(opModLoadLimW.value) in xml
    # output: DERControlResponse = DERControlResponse.from_xml(xml)
    # assert output.DERControlBase_
