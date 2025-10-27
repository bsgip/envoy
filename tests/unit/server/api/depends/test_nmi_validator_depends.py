from envoy.server.manager.nmi_validator import DNSPParticipantId, NmiValidator
from envoy.server.api.depends.nmi_validator import fetch_nmi_validator


def test_fetch_nmi_validator_present(create_request_with_app_state):
    nmi_validator = NmiValidator(DNSPParticipantId.Ausgrid)
    request = create_request_with_app_state(nmi_validator=nmi_validator)
    result = fetch_nmi_validator(request)
    assert result is nmi_validator


def test_fetch_nmi_validator_absent(create_request_with_app_state):
    request = create_request_with_app_state()
    result = fetch_nmi_validator(request)
    assert result is None
