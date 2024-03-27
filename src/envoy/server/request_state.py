from dataclasses import dataclass
from typing import Optional


@dataclass
class RequestStateParameters:
    """Set of parameters inherent to an incoming request - likely specified by fastapi depends"""

    aggregator_id: int  # The aggregator id that a request is scoped to (sourced from auth dependencies)
    aggregator_lfdi: str  # The lfdi associated with the aggregator (source from the client TLS certificate)
    href_prefix: Optional[str]  # If set - all outgoing href's should be prefixed with this value
