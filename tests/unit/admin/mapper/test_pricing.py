""" Basic tests that valid no exceptions are being raised
"""

from datetime import datetime

import pytest
from assertical.asserts.generator import assert_class_instance_equality
from assertical.fake.generator import generate_class_instance
from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest, TariffRequest, TariffResponse

from envoy.admin.mapper.pricing import TariffGeneratedRateListMapper, TariffMapper
from envoy.server.model.tariff import Tariff, TariffGeneratedRate


def test_tariff_mapper_from_request():
    req = generate_class_instance(TariffRequest)
    changed_time = datetime(2023, 4, 5, 6, 7, 8, 9)
    mdl = TariffMapper.map_from_request(changed_time, req)

    assert isinstance(mdl, Tariff)
    assert mdl.changed_time == changed_time
    assert mdl.tariff_id == None  # noqa


def test_tariff_mapper_to_response():
    mdl = generate_class_instance(Tariff)
    mdl.currency_code = 36

    resp = TariffMapper.map_to_response(mdl)

    assert isinstance(resp, TariffResponse)
    assert_class_instance_equality(TariffResponse, mdl, resp)


@pytest.mark.parametrize("optional_is_none", [True, False])
def test_tariff_genrate_mapper_from_request(optional_is_none: bool):
    req: TariffGeneratedRateRequest = generate_class_instance(
        TariffGeneratedRateRequest, optional_is_none=optional_is_none
    )
    changed_time = datetime(2022, 4, 5, 6, 7, 8, 9)
    mdl = TariffGeneratedRateListMapper.map_from_request(changed_time, [req]).pop()

    assert isinstance(mdl, TariffGeneratedRate)

    assert_class_instance_equality(
        TariffGeneratedRate,
        mdl,
        req,
        ignored_properties=set(["tariff_generated_rate_id", "created_time", "changed_time"]),
    )

    assert mdl.changed_time == changed_time
    assert mdl.tariff_generated_rate_id == None  # noqa
    assert mdl.created_time == None, "This should be set in the DB"  # noqa
