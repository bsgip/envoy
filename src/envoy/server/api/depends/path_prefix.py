from fastapi import Request


class PathPrefixDepends:
    """Dependency class for populating the request state href_prefix"""

    href_prefix: str

    def __init__(self, href_prefix: str):
        self.href_prefix = href_prefix

    async def __call__(self, request: Request) -> None:
        request.state.href_prefix = self.href_prefix
