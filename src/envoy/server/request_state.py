from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestStateParameters:
    """Set of parameters inherent to an incoming request - likely specified by fastapi depends

    If:
    aggregator_id is None and site_id is None:
        This request has NO access to anything beyond registering a new edev
    aggregator_id is None and site_id is not None:
        This request cannot access ANY aggregator resources - the only thing it can access is that site_id
    aggregator_id is not None and site_id is None:
        This request can access anything under aggregator_id
    aggregator_id is not None and site_id is not None:
        This is an unsupported case and will raise a ValueError
    """

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    # This can be None if the request does not have access to any aggregator (NOT unscoped access)
    aggregator_id: Optional[int]
    # The site id that a request is scoped to (sourced from auth dependencies)
    # This can be None if the request does not have a single site scope
    site_id: Optional[int]

    lfdi: str  # The lfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    sfdi: int  # The sfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    href_prefix: Optional[str]  # If set - all outgoing href's should be prefixed with this value

    def __post_init__(self) -> None:
        if self.aggregator_id is not None and self.site_id is not None:
            raise ValueError(
                f"RequestStateParameters cannot have both agg {self.aggregator_id} and site {self.site_id}"
            )
