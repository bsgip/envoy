from datetime import datetime, timezone

import pytest
from assertical.asserts.type import assert_list_type
from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.auth import ClientIdDetails, select_all_client_id_details
from tests.data.certificates.certificate1 import TEST_CERTIFICATE_LFDI as CERT1_LFDI
from tests.data.certificates.certificate2 import TEST_CERTIFICATE_LFDI as CERT2_LFDI
from tests.data.certificates.certificate3 import TEST_CERTIFICATE_LFDI as CERT3_LFDI
from tests.data.certificates.certificate4 import TEST_CERTIFICATE_LFDI as CERT4_LFDI
from tests.data.certificates.certificate5 import TEST_CERTIFICATE_LFDI as CERT5_LFDI


@pytest.mark.anyio
async def test_select_all_client_id_details(pg_base_config):
    """Tests that select_all_client_id_details behaves with the base config.
    Base config has 4 active certificates registered. cert3 is expired"""

    async with generate_async_session(pg_base_config) as session:
        # Test the basic config is there and accessible
        result = await select_all_client_id_details(session)

    assert_list_type(ClientIdDetails, result, count=5)
    assert [CERT1_LFDI, CERT2_LFDI, CERT3_LFDI, CERT4_LFDI, CERT5_LFDI] == [r.lfdi for r in result]
    assert [
        datetime(2037, 1, 1, 1, 2, 3, tzinfo=timezone.utc),
        datetime(2037, 1, 1, 2, 3, 4, tzinfo=timezone.utc),
        datetime(2023, 1, 1, 1, 2, 4, tzinfo=timezone.utc),
        datetime(2037, 1, 1, 1, 2, 3, tzinfo=timezone.utc),
        datetime(2037, 1, 1, 1, 2, 3, tzinfo=timezone.utc),
    ] == [r.expiry for r in result]
