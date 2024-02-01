from decimal import Decimal

from fastapi import Request

from envoy.server.model.config.default_doe import DefaultDoeConfiguration


class DefaultDoeDepends:
    """Dependency class for populating the request state default_doe with an instance of DefaultDoeConfiguration"""

    import_limit_active_watts: Decimal
    export_limit_active_watts: Decimal

    def __init__(self, import_limit_active_watts: Decimal, export_limit_active_watts: Decimal):
        self.import_limit_active_watts = import_limit_active_watts
        self.export_limit_active_watts = export_limit_active_watts

    async def __call__(self, request: Request) -> None:
        request.state.default_doe = DefaultDoeConfiguration(
            import_limit_active_watts=self.import_limit_active_watts,
            export_limit_active_watts=self.export_limit_active_watts,
        )
