import unittest.mock as mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from envoy.server.api.depends.xml import AllowEquivalentXmlNsMiddleware


@pytest.mark.allow_eq_xmlns_middleware
async def test_AllowEquivalentXmlNsMiddleware():

    app = FastAPI()
    app.add_middleware(AllowEquivalentXmlNsMiddleware, equivalent_ns_map={b"hi": b"bye"})

    client = TestClient(app)
    response = client.post("/", content=b"hi")
    print(response.content)
