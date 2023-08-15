from envoy.server.settings import AppSettings


def test_dynamic_engine_args():
    """Tests that the dynamic engine args appear/disappear depending on settings"""
    settings_dyn_args = AppSettings(azure_ad_db_resource_id="abc-123", azure_ad_db_refresh_secs=456)
    assert settings_dyn_args.db_middleware_kwargs["engine_args"] == {"pool_recycle": 456}

    settings_dyn_args = AppSettings(azure_ad_db_resource_id=None, azure_ad_db_refresh_secs=789)
    assert "engine_args" not in settings_dyn_args.db_middleware_kwargs
