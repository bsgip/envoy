from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


# TODO: rename to DefaultSiteControlConfiguration as part of DOE->SiteControl refactor.
@dataclass
class DefaultDoeConfiguration:
    """The globally configured Default dynamic operating envelope (DOE) values to be used as a fallback if
    one is/are not defined for a particular site.

    """

    import_limit_active_watts: Optional[Decimal] = None
    export_limit_active_watts: Optional[Decimal] = None
    generation_limit_active_watts: Optional[Decimal] = None
    load_limit_active_watts: Optional[Decimal] = None
    ramp_rate_percent_per_second: Optional[int] = None
