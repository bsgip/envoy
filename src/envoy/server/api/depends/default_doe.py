from decimal import Decimal
from typing import Optional

from fastapi import Request

from envoy.server.model.config.default_doe import DefaultDoeConfiguration


class DefaultDoeDepends:
    """Dependency class for populating the request state default_doe with an instance of DefaultDoeConfiguration"""

    import_limit_active_watts: Optional[Decimal]
    export_limit_active_watts: Optional[Decimal]
    generation_limit_active_watts: Optional[Decimal]
    load_limit_active_watts: Optional[Decimal]
    ramp_rate_percent_per_second: Optional[int]

    def __init__(
        self,
        import_limit_active_watts: Optional[Decimal] = None,
        export_limit_active_watts: Optional[Decimal] = None,
        generation_limit_active_watts: Optional[Decimal] = None,
        load_limit_active_watts: Optional[Decimal] = None,
        ramp_rate_percent_per_second: Optional[int] = None,
    ):
        self.import_limit_active_watts = import_limit_active_watts
        self.export_limit_active_watts = export_limit_active_watts
        self.generation_limit_active_watts = generation_limit_active_watts
        self.load_limit_active_watts = load_limit_active_watts
        self.ramp_rate_percent_per_second = ramp_rate_percent_per_second

    async def __call__(self, request: Request) -> None:
        request.state.default_doe = DefaultDoeConfiguration(
            import_limit_active_watts=self.import_limit_active_watts,
            export_limit_active_watts=self.export_limit_active_watts,
            generation_limit_active_watts=self.generation_limit_active_watts,
            load_limit_active_watts=self.load_limit_active_watts,
            ramp_rate_percent_per_second=self.ramp_rate_percent_per_second,
        )
