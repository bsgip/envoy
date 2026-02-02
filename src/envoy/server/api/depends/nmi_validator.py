from fastapi import Request

from envoy.server.manager.nmi_validator import NmiValidator

NMI_VALIDATOR_ATTR = "nmi_validator"


def fetch_nmi_validator(request: Request) -> NmiValidator | None:
    """Fetches the NmiValidator from FastAPI app state under the expected attribute name.

    Assumes an NmiValidator instance is stored on `app.state` using the key defined
    by `NMI_VALIDATOR_ATTR`, typically set during application startup.

    Returns:
        The NmiValidator instance if found, otherwise None.
    """
    return getattr(request.app.state, NMI_VALIDATOR_ATTR, None)
