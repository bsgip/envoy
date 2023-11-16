from dataclasses import dataclass


@dataclass
class DefaultDoeConfiguration:
    """The globally configured Default dynamic operating envelope (DOE) values to be used in lieu of an active DOE

    This is to support a single static set of values - at some point this will likely be deprecated by something
    in the database
    """

    import_limit_active_watts: int
    export_limit_active_watts: int
