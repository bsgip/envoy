""" Module for XML-specific middleware and depends.
"""

from typing import Awaitable, Callable
from fastapi import Request, Response, FastAPI
from starlette.types import Receive, Scope, Send, Message


class AllowEquivalentXmlNsMiddleware:
    """This middleware is a hacky way of treating multiple namespaces as equivalent to avoid failure in
    namespace validation. To do this we manipulate the incoming request payload and replace the namespaces as defined
    in the 'equivalent_ns_map'. The 'equivalent_ns_map' defines a 'key':'value' map of namespaces to treat as
    equivalent. The 'key' is the incoming namespace which will be replaced by the 'value'. This runs before the
    endpoint function is called (i.e. deserailisation and validation of the request body payload). On the way out, the
    response payload is similarly modified with the 'value' replacing the 'key'.

    Specific usecase: The latest CSIP-AUS standard (v1.1a) introduces a variation to the XML namespace. The original
    namespace http://csipaus.org/ns is now https://csipaus.org/ns. This middlewarre checks for the legacy namespace in
    the request payload and modifies it to the updated namespace. If detected, we also revert to using the
    legacy namespace in the response payload. Note that current thinking is for this is to be a temporary approach in
    support of migration to the new namespace.
    """

    def __init__(self, app: FastAPI, equivalent_ns_map: dict):
        """
        Args:
            app (FastAPI): FastAPI app.
            equivalent_ns_map (dict): dictionary with key being original namespace and value the new namespace.
        """
        self.app = app
        self.equivalent_ns_map: dict[bytes, bytes] = equivalent_ns_map

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Checks incoming request body for any namespaces in the equivalent_ns_map and replaces them, then on response
        these are mapped back to the original namespace.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # namespace map to apply on response body
        response_ns_map: dict[bytes, bytes] = {}

        async def replace_request_namespace():
            message = await receive()
            body = message.get("body", False)
            if body:
                for external_ns, internal_ns in self.equivalent_ns_map.items():
                    # replace oldns with newns, where count=1 i.e. we assume that namespace will only be defined once in the
                    # entire XML tree. NB. If duplicate exists, this will not be replaced and raise a validation exception.
                    if external_ns in body:
                        response_ns_map[internal_ns] = external_ns
                        body = body.replace(external_ns, internal_ns, 1)
                message["body"] = body
            return message

        async def replace_response_namespace(message: Message):
            if message["type"] == "http.response.body":
                body = message.get("body", False)
                if body:
                    for internal_ns, external_ns in response_ns_map.items():
                        body = body.replace(internal_ns, external_ns, 1)
                    message["body"] = body
            await send(message)

        await self.app(scope, replace_request_namespace, replace_response_namespace)

    # async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:

    #     body = await request.body()

    #     # map from request NS
    #     response_ns_map: dict[bytes, bytes] = {}
    #     for oldns, newns in self.equivalent_ns_map.items():
    #         # replace oldns with newns, where count=1 i.e. we assume that namespace will only be defined once in the
    #         # entire XML tree. NB. If duplicate exists, this will not be replaced and raise a validation exception.
    #         if oldns in body:
    #             response_ns_map[newns] = oldns
    #             body = body.replace(oldns, newns, 1)

    #     # Call route function
    #     request._body = body
    #     response = await call_next(request)

    #     # map back to request NS
    #     for oldns, newns in self.response_ns_map.items():
    #         response.body = response.body.replace(oldns, newns, 1)

    #     return response
