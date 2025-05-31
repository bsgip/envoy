from typing import Optional
from unittest import mock

import pytest
from assertical.fixtures.postgres import generate_async_session

from envoy.server.manager.server import RuntimeServerConfigManager, _map_server_config
from envoy.server.model.config.server import RuntimeServerConfig as domain_mdl
from envoy.server.model.server import RuntimeServerConfig as entity_mdl


@pytest.mark.parametrize(
    "entity, default_domain, expected_domain",
    [
        (
            entity_mdl(
                runtime_server_config_id=1,
                dcap_pollrate_seconds=2,
                edevl_pollrate_seconds=3,
                fsal_pollrate_seconds=4,
                derpl_pollrate_seconds=5,
                derl_pollrate_seconds=6,
                mup_postrate_seconds=7,
                site_control_pow10_encoding=8,
                disable_edev_registration=True,
            ),
            domain_mdl(),
            domain_mdl(
                dcap_pollrate_seconds=2,
                edevl_pollrate_seconds=3,
                fsal_pollrate_seconds=4,
                derpl_pollrate_seconds=5,
                derl_pollrate_seconds=6,
                mup_postrate_seconds=7,
                site_control_pow10_encoding=8,
                disable_edev_registration=True,
            ),
        ),
        (
            entity_mdl(
                runtime_server_config_id=1,
                dcap_pollrate_seconds=2,
                edevl_pollrate_seconds=3,
                fsal_pollrate_seconds=4,
                derpl_pollrate_seconds=5,
                derl_pollrate_seconds=None,
                mup_postrate_seconds=None,
                site_control_pow10_encoding=None,
                disable_edev_registration=None,
            ),
            domain_mdl(
                derl_pollrate_seconds=16,
                mup_postrate_seconds=17,
                site_control_pow10_encoding=18,
                disable_edev_registration=True,
            ),
            domain_mdl(
                dcap_pollrate_seconds=2,
                edevl_pollrate_seconds=3,
                fsal_pollrate_seconds=4,
                derpl_pollrate_seconds=5,
                derl_pollrate_seconds=16,
                mup_postrate_seconds=17,
                site_control_pow10_encoding=18,
                disable_edev_registration=True,
            ),
        ),
        (None, domain_mdl(), domain_mdl()),
    ],
)
def test_map_server_config(entity: Optional[entity_mdl], default_domain: domain_mdl, expected_domain: domain_mdl):

    # Act
    with mock.patch("envoy.server.manager.server.default", default_domain):  # replace default with test instance
        res = _map_server_config(entity)

    # Assert
    assert res == expected_domain


@pytest.mark.anyio
async def test_manager_fetch_current_config(pg_base_config):
    """Basic success test"""
    # Arrange

    # Act
    async with generate_async_session(pg_base_config) as session:
        cfg = await RuntimeServerConfigManager.fetch_current_config(session)

    # Assert
    assert cfg.dcap_pollrate_seconds == 300
    assert cfg.edevl_pollrate_seconds == 300
    assert cfg.fsal_pollrate_seconds == 300
    assert cfg.derpl_pollrate_seconds == 60
    assert cfg.derl_pollrate_seconds == 60
    assert cfg.mup_postrate_seconds == 60
    assert cfg.site_control_pow10_encoding == -2
    assert cfg.disable_edev_registration is False
