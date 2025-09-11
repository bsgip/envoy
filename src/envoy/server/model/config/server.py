from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RuntimeServerConfig:
    """Internal Domain model that represents runtime server configurations that can be varied dynamically."""

    dcap_pollrate_seconds: int = 300
    edevl_pollrate_seconds: int = 300
    fsal_pollrate_seconds: int = 300
    derpl_pollrate_seconds: int = 60
    derl_pollrate_seconds: int = 60
    mup_postrate_seconds: int = 60
    site_control_pow10_encoding: int = 0
    disable_edev_registration: bool = False
