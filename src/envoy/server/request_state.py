from dataclasses import dataclass
from typing import Optional


@dataclass
class RequestStateParameters:
    """Set of parameters inherent to an incoming request - likely specified by fastapi depends"""

    aggregator_id: int  # The aggregator id that a request is scoped to (sourced from auth dependencies)
    href_prefix: Optional[str]  # If set - all outgoing href's should be prefixed with this value
