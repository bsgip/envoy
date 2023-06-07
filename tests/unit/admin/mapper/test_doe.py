from random import randint

from envoy.admin.mapper.doe import DoeMapper
from envoy.admin.schema.doe import DynamicOperatingEnvelopeAdminRequest, DynamicOperatingEnvelopeAdminResponse
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.data.fake.generator import generate_class_instance


def test_doe_mapper_from_request():
    req: DynamicOperatingEnvelopeAdminRequest = generate_class_instance(
        DynamicOperatingEnvelopeAdminRequest, seed=randint(1, 100)
    )

    mdl = DoeMapper.map_from_request(req)

    assert isinstance(mdl, DynamicOperatingEnvelope)

    assert mdl.site_id == req.site_id
    assert mdl.duration_seconds == req.duration_seconds
    assert mdl.import_limit_active_watts == req.import_limit_active_watts
    assert mdl.export_limit_watts == req.export_limit_watts

    assert mdl.changed_time

    # A DynamicOperatingEnvelope from mapping does not have a site, but it does have a site_id.
    # Should it get the associated site by site_id? TODO
    assert not mdl.site
    assert not mdl.dynamic_operating_envelope_id


def test_doe_mapper_to_response():
    mdl: DynamicOperatingEnvelope = generate_class_instance(
        DynamicOperatingEnvelope, seed=randint(1, 100), generate_relationships=True
    )

    resp = DoeMapper.map_to_response(mdl)

    assert isinstance(resp, DynamicOperatingEnvelopeAdminResponse)

    assert resp.dynamic_operating_envelope_id == mdl.dynamic_operating_envelope_id
    assert resp.site_id == mdl.site_id
    assert resp.site == mdl.site
    assert resp.changed_time == mdl.changed_time
    assert resp.duration_seconds == mdl.duration_seconds
    assert resp.import_limit_active_watts == mdl.import_limit_active_watts
    assert resp.export_limit_watts == mdl.export_limit_watts
