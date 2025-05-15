from dataclasses import dataclass
from decimal import Decimal


@dataclass
class DefaultSiteControlConfiguration:
    """The globally configured Default site control values to be used as a fallback if
    a default site control is not defined for a particular site.
    """

    import_limit_active_watts: Decimal
    export_limit_active_watts: Decimal
    generation_limit_watts: Decimal
    load_limit_watts: Decimal
    ramp_rate_percent_per_second: Decimal
