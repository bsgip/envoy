from typing import Optional

import pytest

from envoy.server.crud.auth import ClientIdDetails, select_client_ids_using_lfdi
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_LFDI as cert1_lfdi_active_agg1
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_LFDI as cert2_lfdi_active_agg1
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_LFDI as cert3_lfdi_expired_agg1
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_LFDI as cert4_lfdi_active_agg2
from tests.data.certificates.certificate_noreg import TEST_CERTIFICATE_LFDI as cert_noreg_lfdi
from tests.postgres_testing import generate_async_session


@pytest.mark.parametrize(
    "lfdi, expected_cert_id, expected_agg_id",
    [
        (cert1_lfdi_active_agg1, 1, 1),
        (cert2_lfdi_active_agg1, 2, 1),
        (cert3_lfdi_expired_agg1, None, None),  # This is an expired cert
        (cert4_lfdi_active_agg2, 4, 2),
        ("", None, None),  # bad LFDI
        (cert_noreg_lfdi, None, None),  # unregistered LFDI
        (cert1_lfdi_active_agg1 + "a", None, None),  # unregistered LFDI
        ("' --", None, None),  # bad LFDI
    ],
)
@pytest.mark.anyio
async def test_select_client_ids_using_lfdi(
    pg_base_config, lfdi: str, expected_cert_id: Optional[int], expected_agg_id: Optional[int]
):
    """Tests that select_client_ids_using_lfdi behaves with the base config"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        result = await select_client_ids_using_lfdi(lfdi, session)
        if expected_cert_id is None or expected_agg_id is None:
            assert result is None
        else:
            assert result == ClientIdDetails(certificate_id=expected_cert_id, aggregator_id=expected_agg_id)
