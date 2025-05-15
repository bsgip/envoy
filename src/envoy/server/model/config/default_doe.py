from dataclasses import dataclass
from decimal import Decimal


# TODO: rename to DefaultSiteControlConfiguration as part of DOE->SiteControl refactor.
@dataclass
class DefaultDoeConfiguration:
    """The globally configured Default dynamic operating envelope (DOE) values to be used as a fallback if
    one is/are not defined for a particular site.

    """

    import_limit_active_watts: Decimal
    export_limit_active_watts: Decimal
    generation_limit_active_watts: Decimal
    load_limit_active_watts: Decimal
    ramp_rate_percent_per_second: Decimal
