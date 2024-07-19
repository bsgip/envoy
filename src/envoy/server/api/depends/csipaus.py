""" Module for CSIP-Australia specific middleware and depends.
"""

from fastapi import FastAPI
from starlette.types import Receive, Scope, Send, Message


class CSIPV11aXmlNsOptInMiddleware:
    """The latest CSIP-AUS standard (v1.1a) introduces a variation to the XML namespace. The v1.1 namespace
    http://csipaus.org/ns is now https://csipaus.org/ns in v1.1a. This middlewarre checks for the a boolean opt-out
    header in the request and if set to True, we allow the use of the legacy namespace both in incoming and outgoing.
    legacy namespace in the response payload. Note that current thinking is for this is to be a temporary approach in
    support of migration to the new namespace.

    NB. The assumption is we use the V1.1a namespace internally in our validation models.
    """

    equivalent_ns_map: tuple[bytes, bytes] = (b"http://csipaus.org/ns", b"https://csipaus.org/ns")  # (v1.1 , v1.1a)
    opt_in_header_name: str = "x-csip-v11a-opt-in"

    def __init__(self, app: FastAPI):
        """
        Args:
            app (FastAPI): FastAPI app.
        """
        self.app = app

    def check_opt_in_header(self, scope: Scope) -> bool:
        # Check of v1.1a opt-in header
        for header_name, _ in scope["headers"]:
            if self.opt_in_header_name.encode("utf-8") == header_name:
                return True
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Checks incoming request body for any namespaces in the equivalent_ns_map and replaces them, then on response
        these are mapped back to the original namespace.
        """
        # Skip running this middleware if opt-in header is not found
        if scope["type"] != "http" or self.check_opt_in_header(scope):
            await self.app(scope, receive, send)
            return

        async def replace_request_namespace() -> Message:
            message = await receive()
            body = message.get("body", False)
            if body:
                body = body.replace(self.equivalent_ns_map[0], self.equivalent_ns_map[1], 1)
                message["body"] = body
            return message

        async def replace_response_namespace(message: Message) -> None:
            if message["type"] == "http.response.body":
                body = message.get("body", False)
                if body:
                    body = body.replace(self.equivalent_ns_map[1], self.equivalent_ns_map[0], 1)
                    message["body"] = body
            await send(message)

        await self.app(scope, replace_request_namespace, replace_response_namespace)
