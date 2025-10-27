from typing import Any
import pytest

from fastapi import FastAPI, Request
from starlette.datastructures import State


@pytest.fixture(scope="function")
def create_request_with_app_state():
    def func(**state: dict[str, Any]) -> Request:
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

    return func
