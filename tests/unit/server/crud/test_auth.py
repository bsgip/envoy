import pytest

from server.crud.auth import select_client_ids_using_lfdi
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_LFDI as cert1_lfdi_active_agg1
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_LFDI as cert2_lfdi_active_agg1
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_LFDI as cert3_lfdi_expired_agg1
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_LFDI as cert4_lfdi_active_agg2
from tests.data.certificates.certificate_noreg import TEST_CERTIFICATE_LFDI as cert_noreg_lfdi
from tests.postgres_testing import generate_async_session


@pytest.mark.anyio
async def test_select_client_ids_using_lfdi(pg_base_config):
    """Tests that select_client_ids_using_lfdi behaves with the base config"""
    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        assert await select_client_ids_using_lfdi(cert1_lfdi_active_agg1, session) == {
            "certificate_id": 1,
            "aggregator_id": 1,
        }

        assert await select_client_ids_using_lfdi(cert2_lfdi_active_agg1, session) == {
            "certificate_id": 2,
            "aggregator_id": 1,
        }

        # This is an expired cert
        assert await select_client_ids_using_lfdi(cert3_lfdi_expired_agg1, session) is None

        assert await select_client_ids_using_lfdi(cert4_lfdi_active_agg2, session) == {
            "certificate_id": 4,
            "aggregator_id": 2,
        }

        # Test bad LFDIs
        assert await select_client_ids_using_lfdi('', session) is None
        assert await select_client_ids_using_lfdi(cert_noreg_lfdi, session) is None
        assert await select_client_ids_using_lfdi(cert1_lfdi_active_agg1 + "a", session) is None
        assert await select_client_ids_using_lfdi('\' --', session) is None
