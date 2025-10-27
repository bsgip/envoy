from envoy.server.api.depends.allow_nmi_updates import (
    ALLOW_NMI_UPDATES_ATTR,
    DEFAULT_ALLOW_NMI_UPDATES,
    fetch_allow_nmi_updates_setting,
)


def test_fetch_nmi_validator_present(create_request_with_app_state):
    request = create_request_with_app_state(**{ALLOW_NMI_UPDATES_ATTR: False})
    result = fetch_allow_nmi_updates_setting(request)
    assert result is False


def test_fetch_nmi_validator_absent(create_request_with_app_state):
    request = create_request_with_app_state()
    result = fetch_allow_nmi_updates_setting(request)
    assert result is DEFAULT_ALLOW_NMI_UPDATES
