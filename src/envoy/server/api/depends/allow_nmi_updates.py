from fastapi import Request


ALLOW_NMI_UPDATES_ATTR = "allow_nmi_updates"
DEFAULT_ALLOW_NMI_UPDATES = True


def fetch_allow_nmi_updates_setting(request: Request) -> bool:
    """Fetches the ALLOW_NMI_UPDATES setting from FastAPI app state under the expected attribute name."""
    return getattr(request.app.state, ALLOW_NMI_UPDATES_ATTR, DEFAULT_ALLOW_NMI_UPDATES)
