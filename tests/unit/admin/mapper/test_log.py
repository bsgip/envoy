from datetime import datetime

import pytest
from envoy_schema.admin.schema.log import CalculationLogRequest, CalculationLogResponse

from envoy.admin.mapper.log import CalculationLogMapper
from envoy.server.model.log import CalculationLog
from tests.data.fake.generator import assert_class_instance_equality, generate_class_instance


@pytest.mark.parametrize("optional_as_none", [True, False])
def test_log_mapper_roundtrip(optional_as_none: bool):
    original: CalculationLog = generate_class_instance(
        CalculationLog, optional_is_none=optional_as_none, generate_relationships=True
    )

    changed_time = datetime(2021, 5, 6, 7, 8, 9)
    intermediate_model = CalculationLogMapper.map_to_response(original)
    assert isinstance(intermediate_model, CalculationLogResponse)

    actual = CalculationLogMapper.map_from_request(changed_time, intermediate_model)
    assert isinstance(actual, CalculationLog)

    assert_class_instance_equality(CalculationLog, original, actual, ignored_properties=set(["created_time"]))
    assert actual.created_time == changed_time
