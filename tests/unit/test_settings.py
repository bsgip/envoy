import os

import pytest
from assertical.fixtures.environment import delete_environment_variable
from pydantic import PostgresDsn
from pydantic_core import ValidationError

from envoy.settings import CommonSettings, generate_middleware_kwargs

TEST_DATABASE_URL = "postgresql+asyncpg://u:p@localhost:1122/mydb"  # Should validate as a valid postgresql DSN


def remove_mandatory_settings():
    delete_environment_variable("DATABASE_URL")


def test_settings_missing_mandatory(preserved_environment):
    """Do we get errors if the mandatory setting keys are missing"""
    remove_mandatory_settings()
    with pytest.raises(ValidationError):
        CommonSettings(_env_file=None)


def test_settings_defaults(preserved_environment):
    """Don't set any config values - just let it load with defaults and no errors"""

    # Reset config
    remove_mandatory_settings()
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    settings = CommonSettings()

    assert settings.enable_notifications is None
    assert settings.sqlalchemy_engine_arguments is None
    assert settings.database_url == PostgresDsn(TEST_DATABASE_URL)
    assert isinstance(settings.db_middleware_kwargs, dict)


def test_settings_engine_args(preserved_environment):
    """Don't set any config values - just let it load with defaults and no errors"""

    # Reset config
    remove_mandatory_settings()
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["SQLALCHEMY_ENGINE_ARGUMENTS"] = '{"foo": "bar", "num": 123, "bool": true, "float": 1.23}'

    settings = CommonSettings()
    assert settings.sqlalchemy_engine_arguments == {"foo": "bar", "num": 123, "bool": True, "float": 1.23}


def test_generate_middleware_kwargs():

    kwargs_defaults = generate_middleware_kwargs(TEST_DATABASE_URL, True, None, None, None)
    assert isinstance(kwargs_defaults, dict)
    assert kwargs_defaults["db_url"] == TEST_DATABASE_URL
    assert kwargs_defaults["commit_on_exit"] is True
    assert "engine_args" not in kwargs_defaults

    kwargs_values = generate_middleware_kwargs(
        TEST_DATABASE_URL, False, {"foo": "bar", "num": 123, "bool": True}, "resource_id", 456
    )
    assert isinstance(kwargs_values, dict)
    assert kwargs_values["db_url"] == TEST_DATABASE_URL
    assert kwargs_values["commit_on_exit"] is False
    assert kwargs_values["engine_args"] == {"pool_recycle": 456, "foo": "bar", "num": 123, "bool": True}
