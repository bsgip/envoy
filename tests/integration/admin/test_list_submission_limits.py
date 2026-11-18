from http import HTTPStatus

import pytest
from assertical.fake.generator import generate_class_instance
from assertical.fixtures.postgres import generate_async_session
from envoy_schema.admin.schema.certificate import CertificateAssignmentRequest
from envoy_schema.admin.schema.pricing import TariffGeneratedRateRequest
from envoy_schema.admin.schema.site_control import SiteControlRequest
from envoy_schema.admin.schema.uri import (
    AggregatorCertificateListUri,
    SiteControlUri,
    TariffGeneratedRateCreateUri,
)
from httpx import AsyncClient
from sqlalchemy import func, select

from envoy.admin.api.validation import MAX_ADMIN_LIST_SUBMISSION
from envoy.server.model.aggregator import AggregatorCertificateAssignment
from envoy.server.model.doe import DynamicOperatingEnvelope
from envoy.server.model.tariff import TariffGeneratedRate


def _build_items(count: int, factory) -> str:
    return "[" + ",".join(factory(i).model_dump_json() for i in range(count)) + "]"


@pytest.mark.parametrize(
    "uri, factory, model_type",
    [
        (
            SiteControlUri.format(group_id=1),
            lambda i: generate_class_instance(SiteControlRequest, seed=i, site_group_id=2),
            DynamicOperatingEnvelope,
        ),
        (
            TariffGeneratedRateCreateUri,
            lambda i: generate_class_instance(
                TariffGeneratedRateRequest, seed=i, tariff_component_id=1, site_group_id=1
            ),
            TariffGeneratedRate,
        ),
        (
            AggregatorCertificateListUri.format(aggregator_id=1),
            lambda i: CertificateAssignmentRequest(certificate_id=(i % 5) + 1),
            AggregatorCertificateAssignment,
        ),
    ],
)
@pytest.mark.anyio
async def test_bulk_submission_exceeding_max_is_rejected(
    pg_base_config, admin_client_auth: AsyncClient, uri: str, factory, model_type
):
    """Bulk list submissions larger than MAX_ADMIN_LIST_SUBMISSION should be rejected with BadRequest and nothing
    should be persisted"""
    async with generate_async_session(pg_base_config) as session:
        before_count = (await session.execute(select(func.count()).select_from(model_type))).scalar_one()

    resp = await admin_client_auth.post(uri, content=_build_items(MAX_ADMIN_LIST_SUBMISSION + 1, factory))
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    async with generate_async_session(pg_base_config) as session:
        after_count = (await session.execute(select(func.count()).select_from(model_type))).scalar_one()
    assert before_count == after_count
