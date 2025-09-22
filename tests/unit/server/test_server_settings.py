import os

import pytest

from envoy.server.manager.nmi_validator import DNSPParticipantId, NmiValidator
from envoy.server.settings import AppSettings, NmiValidationSettings


def test_dynamic_engine_args():
    """Tests that the dynamic engine args appear/disappear depending on settings"""
    settings_dyn_args = AppSettings(azure_ad_db_resource_id="abc-123", azure_ad_db_refresh_secs=456)
    assert settings_dyn_args.db_middleware_kwargs["engine_args"] == {"pool_recycle": 456}

    settings_dyn_args = AppSettings(azure_ad_db_resource_id=None, azure_ad_db_refresh_secs=789)
    assert "engine_args" not in settings_dyn_args.db_middleware_kwargs


def test_nmi_validation_settings(preserved_environment):
    """Test validator property works"""
    # Arrange
    os.environ["nmi_validation_enabled"] = "true"
    os.environ["nmi_validation_participant_id"] = DNSPParticipantId.Ausgrid

    # Act
    settings = NmiValidationSettings()

    # Assert
    assert settings.nmi_validation_enabled
    assert settings.nmi_validation_participant_id == DNSPParticipantId.Ausgrid
    assert isinstance(settings.validator, NmiValidator)


def test_nmi_validation_settings_invalid_participant_id(preserved_environment):
    """Settings should raise ValueError if invalid participant id is defined."""
    # Arrange
    os.environ["nmi_validation_participant_id"] = "invalid"

    # Act / Assert
    with pytest.raises(ValueError):
        NmiValidationSettings()


def test_nmi_validation_settings_no_participant_id(preserved_environment):
    """Settings should raise ValueError if enabled and no participant id is defined."""
    # Arrange
    os.environ["nmi_validation_enabled"] = "true"

    # Act / Assert
    with pytest.raises(ValueError):
        NmiValidationSettings()
