from datetime import datetime, timezone
from typing import Optional
import pytest

from assertical.fixtures.postgres import generate_async_session

from envoy.server.crud.server import select_server_config
from envoy.server.model.server import RuntimeServerConfig


def entity_to_dict(instance):
    return {c.name: getattr(instance, c.name) for c in instance.__table__.columns}


@pytest.mark.parametrize(
    "expected",
    [
        (None),
        (
            RuntimeServerConfig(
                runtime_server_config_id=1,
                changed_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                created_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                dcap_pollrate_seconds=1,
                edevl_pollrate_seconds=2,
                fsal_pollrate_seconds=3,
                derpl_pollrate_seconds=4,
                derl_pollrate_seconds=5,
                mup_postrate_seconds=6,
                site_control_pow10_encoding=7,
            )
        ),
        (
            RuntimeServerConfig(
                runtime_server_config_id=1,
                changed_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                created_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                dcap_pollrate_seconds=10,
                edevl_pollrate_seconds=20,
                fsal_pollrate_seconds=30,
                derpl_pollrate_seconds=40,
                derl_pollrate_seconds=50,
                mup_postrate_seconds=60,
                site_control_pow10_encoding=70,
            )
        ),
    ],
)
@pytest.mark.anyio
async def test_select_server_config(pg_base_config, expected: Optional[RuntimeServerConfig]):
    """Basic success test"""
    # Arrange
    if expected:
        pg_base_config.execute(
            f"""UPDATE runtime_server_config
            SET created_time='{expected.created_time.isoformat()}',
                changed_time='{expected.changed_time.isoformat()}',
                dcap_pollrate_seconds={expected.dcap_pollrate_seconds},
                edevl_pollrate_seconds={expected.edevl_pollrate_seconds},
                fsal_pollrate_seconds={expected.fsal_pollrate_seconds},
                derpl_pollrate_seconds={expected.derpl_pollrate_seconds},
                derl_pollrate_seconds={expected.derl_pollrate_seconds},
                mup_postrate_seconds={expected.mup_postrate_seconds},
                site_control_pow10_encoding={expected.site_control_pow10_encoding}
            WHERE runtime_server_config_id=1;
            """
        )
    else:
        pg_base_config.execute("DELETE FROM runtime_server_config;")
    pg_base_config.commit()

    # Act
    async with generate_async_session(pg_base_config) as session:
        res = await select_server_config(session)

    # Assert
    if expected is None:
        assert res == expected
    else:
        assert entity_to_dict(res) == entity_to_dict(expected)
