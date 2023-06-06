""" Basic tests that valid no exceptions are being raised
"""
import pytest
from random import randint

from envoy.admin.mapper.pricing import TariffMapper, TariffGeneratedRateListMapper
from envoy.admin.schema.pricing import (
    TariffRequest,
    TariffResponse,
    TariffGeneratedRateRequest,
)
from envoy.server.model.tariff import Tariff, TariffGeneratedRate

from tests.data.fake.generator import generate_class_instance, assert_class_instance_equality


def test_tariff_mapper_from_request():
    req = generate_class_instance(TariffRequest, seed=randint(1, 100))

    mdl = TariffMapper.map_from_request(req)

    assert isinstance(mdl, Tariff)
    assert mdl.changed_time
    assert mdl.tariff_id == None  # noqa


def test_tariff_mapper_to_response():
    mdl = generate_class_instance(Tariff, seed=randint(1, 100))
    mdl.currency_code = 36

    resp = TariffMapper.map_to_response(mdl)

    assert isinstance(resp, TariffResponse)
    assert resp.changed_time
    assert resp.tariff_id


def test_tariff_genrate_mapper_from_request():
    req = generate_class_instance(TariffGeneratedRateRequest, seed=randint(1, 100))

    mdl = TariffGeneratedRateListMapper.map_from_request([req]).pop()

    assert isinstance(mdl, TariffGeneratedRate)
    assert mdl.changed_time
    assert mdl.tariff_generated_rate_id == None  # noqa
    assert mdl.tariff_id
    assert mdl.site_id
