""" Module for CSIP-Australia specific middleware and depends.
"""

from fastapi import FastAPI
from starlette.types import Receive, Scope, Send, Message
from starlette.datastructures import MutableHeaders


class CSIPV11aXmlNsOptInMiddleware:
    """The latest CSIP-AUS standard (v1.1a) introduces a variation to the XML namespace. The v1.1 namespace
    http://csipaus.org/ns is now https://csipaus.org/ns in v1.1a. This middlewarre checks for the a boolean opt-out
    header in the request and if set to True, we allow the use of the legacy namespace both in incoming and outgoing.
    legacy namespace in the response payload. Note that current thinking is for this is to be a temporary approach in
    support of migration to the new namespace.

    Notes:
    * The assumption is we use the V1.1a namespace internally in our validation models.
    * This is a pure ASGIMiddleware as defined here: https://www.starlette.io/middleware/#pure-asgi-middleware.
    * Full implementation based off brotli middleware package example
    (https://github.com/fullonic/brotli-asgi/blob/master/brotli_asgi/__init__.py).
    """

    equivalent_ns_map: tuple[bytes, bytes] = (b"http://csipaus.org/ns", b"https://csipaus.org/ns")  # (v1.1 , v1.1a)
    opt_in_header_name: str = "x-csip-v11a-opt-in"

    def __init__(self, app: FastAPI):
        """
        Args:
            app (FastAPI): FastAPI app.
        """
        self.app: FastAPI = app

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

        # The scope["type"] != "http" is Starlette/asgi kludge or a type defined the asgi spec.
        # It can be lifespan, http or websocket. We only want to run our middleware on http.
        # (ref: https://www.starlette.io/middleware/#pure-asgi-middleware)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip running this middleware if opt-in header is not found.
        if self.check_opt_in_header(scope):
            await self.app(scope, receive, send)
            return

        resp_initial_message: Message = {}  # This initial message holds the headers and status code
        resp_original_body: bytearray = bytearray()  # This will be used to accumulate the body sent from Starlette
        sent_init_msg: bool = False  #

        async def replace_request_namespace() -> Message:
            message = await receive()
            body = message.get("body", False)
            if body:
                body = body.replace(self.equivalent_ns_map[0], self.equivalent_ns_map[1], 1)
                message["body"] = body
            return message

        async def replace_response_namespace(message: Message) -> None:
            nonlocal resp_initial_message, resp_original_body, sent_init_msg

            if message["type"] == "http.response.start":
                # This initial message holds the headers. We will not send it until we have updated
                # the content-length header after receiving and modifying the response body.
                # NB. Refer here (https://www.starlette.io/responses/) for how response message
                # is formed (Starlette will automatically include a Content-Length header).
                resp_initial_message = message

            elif message["type"] == "http.response.body":
                more_body = message.get("more_body", False)

                # accumulate the body from the response stream
                resp_original_body.extend(message.get("body", b""))

                # no more body, we can now update content-length
                if not more_body:
                    resp_original_body = resp_original_body.replace(
                        self.equivalent_ns_map[1], self.equivalent_ns_map[0], 1
                    )
                    message["body"] = resp_original_body
                    headers = MutableHeaders(
                        raw=resp_initial_message["headers"]
                    )  # Headers/MutableHeaders are case-insensitive multidicts
                    headers["Content-Length"] = str(len(resp_original_body))

                    sent_init_msg = True  # should never have sent the initial message until this point
                    await send(resp_initial_message)
                    await send(message)

            else:
                if not sent_init_msg:
                    await send(resp_initial_message)
                    sent_init_msg = True
                await send(message)

        await self.app(scope, replace_request_namespace, replace_response_namespace)
