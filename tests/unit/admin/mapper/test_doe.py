from random import randint

from envoy_schema.admin.schema.doe import DynamicOperatingEnvelopeRequest

from envoy.admin.mapper.doe import DoeListMapper
from envoy.server.model.doe import DynamicOperatingEnvelope
from tests.data.fake.generator import generate_class_instance


def test_doe_mapper_from_request():
    req: DynamicOperatingEnvelopeRequest = generate_class_instance(DynamicOperatingEnvelopeRequest)

    mdl = DoeListMapper.map_from_request([req])[0]

    assert isinstance(mdl, DynamicOperatingEnvelope)

    assert mdl.site_id == req.site_id
    assert mdl.duration_seconds == req.duration_seconds
    assert mdl.import_limit_active_watts == req.import_limit_active_watts
    assert mdl.export_limit_watts == req.export_limit_watts
    assert mdl.start_time == req.start_time
    assert mdl.changed_time

    assert not mdl.site
    assert not mdl.dynamic_operating_envelope_id
