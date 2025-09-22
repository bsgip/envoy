from typing import Any
from fastapi import FastAPI, Request
from starlette.datastructures import State

from envoy.server.manager.nmi_validator import DNSPParticipantId, NmiValidator
from envoy.server.api.depends.nmi_validator import fetch_nmi_validator


def create_request_with_app_state(**state: dict[str, Any]) -> Request:
    """Create a FastAPI Request object with a mocked app.state."""
    app = FastAPI()
    app.state = State(state)

    scope = {
        "type": "http",
        "app": app,
        "method": "GET",
        "path": "/",
        "headers": [],
    }

    return Request(scope)


def test_fetch_nmi_validator_present():
    nmi_validator = NmiValidator(DNSPParticipantId.Ausgrid)
    request = create_request_with_app_state(nmi_validator=nmi_validator)
    result = fetch_nmi_validator(request)
    assert result is nmi_validator


def test_fetch_nmi_validator_absent():
    request = create_request_with_app_state()
    result = fetch_nmi_validator(request)
    assert result is None
