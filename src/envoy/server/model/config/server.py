from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RuntimeServerConfig:
    """Represents the runtime server configurations."""

    dcap_pollrate_seconds: int = 300
    edevl_pollrate_seconds: int = 300
    fsal_pollrate_seconds: int = 300
    derpl_pollrate_seconds: int = 60
    derl_pollrate_seconds: int = 60
    mup_postrate_seconds: int = 60
