import pytest
from assertical.asserts import generator as asserts_generator
from assertical.fake import generator as fake_generator
from envoy_schema.admin.schema.certificate import CertificateResponse, CertificatePageResponse

from envoy.admin import mapper
from envoy.server import model


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_certificate_to_response(optional_is_none: bool) -> None:
    """Asserts that the type mapping is a straight passthrough of properties"""
    cert: model.Certificate = fake_generator.generate_class_instance(
        model.Certificate, optional_is_none=optional_is_none
    )
    mdl = mapper.CertificateMapper.map_to_response(cert)

    assert isinstance(mdl, CertificateResponse)

    asserts_generator.assert_class_instance_equality(CertificateResponse, cert, mdl)


def test_aggregator_to_page_response() -> None:
    """aggregator_to_page_response() method happy path"""
    cert1: model.Certificate = fake_generator.generate_class_instance(
        model.Certificate, seed=101, optional_is_none=True, generate_relationships=True
    )
    cert2: model.Certificate = fake_generator.generate_class_instance(
        model.Certificate, seed=202, optional_is_none=False, generate_relationships=False
    )
    total_count = 11
    start = 22
    limit = 33
    mdl = mapper.CertificateMapper.map_to_page_response(total_count, start, limit, [cert1, cert2])

    assert isinstance(mdl, CertificatePageResponse)
    assert len(mdl.certificates) == 2
    assert all([isinstance(a, CertificateResponse) for a in mdl.certificates])
    assert mdl.limit == limit
    assert mdl.start == start
    assert mdl.total_count == total_count
