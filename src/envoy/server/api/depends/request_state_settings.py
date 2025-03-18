from typing import Optional

from fastapi import Request


class RequestStateSettingsDepends:
    """Dependency class for populating the request state href_prefix and iana_pen"""

    href_prefix: Optional[str]
    iana_pen: int

    def __init__(self, href_prefix: Optional[str], iana_pen: int):
        self.href_prefix = href_prefix
        self.iana_pen = iana_pen

    async def __call__(self, request: Request) -> None:
        request.state.iana_pen = self.iana_pen
        if self.href_prefix:
            request.state.href_prefix = self.href_prefix
