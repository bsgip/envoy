import importlib.metadata
from typing import Any, Dict, Optional

from envoy.settings import CommonSettings


class AppSettings(CommonSettings):

    debug: bool = False
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "envoy"
    version: str = importlib.metadata.version("envoy")

    cert_header: str = "x-forwarded-client-cert"  # either client certificate in PEM format or the sha256 fingerprint

    default_doe_import_active_watts: Optional[str] = None  # Constant default DERControl import as a decimal float
    default_doe_export_active_watts: Optional[str] = None  # Constant default DERControl export as a decimal float

    install_csip_v11a_opt_in_middleware: Optional[bool] = (
        False  # Flag whether to install the envoy.server.api.depends.csipaus.AllowEquivalentXmlNsMiddleware
    )

    allow_device_registration: bool = False  # True: LFDI auth will allow unknown certs to register single EndDevices

    @property
    def fastapi_kwargs(self) -> Dict[str, Any]:
        return {
            "debug": self.debug,
            "docs_url": self.docs_url,
            "openapi_prefix": self.openapi_prefix,
            "openapi_url": self.openapi_url,
            "redoc_url": self.redoc_url,
            "title": self.title,
            "version": self.version,
        }


def generate_settings() -> AppSettings:
    """Generates and configures a new instance of the AppSettings"""

    # Silenced complaints about database_url - keeping mypy happy here is tricky (for certain python versions).
    # The "cost" of not having it set will be caught by our test coverage - this is an error we can ignore
    return AppSettings()  # type: ignore  [call-arg]


settings = generate_settings()
