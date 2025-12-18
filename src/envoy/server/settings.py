import importlib.metadata
from functools import cached_property
from typing import Any, Dict, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from envoy.server.api.depends.allow_nmi_updates import DEFAULT_ALLOW_NMI_UPDATES
from envoy.server.endpoint_exclusion import EndpointExclusionSet
from envoy.server.manager.nmi_validator import DNSPParticipantId, NmiValidator
from envoy.settings import CommonSettings


class NmiValidationSettings(BaseSettings):
    nmi_validation_enabled: bool = False
    nmi_validation_participant_id: DNSPParticipantId | None = None

    @model_validator(mode="after")
    def check_participant_id_required(self) -> "NmiValidationSettings":
        if self.nmi_validation_enabled and not self.nmi_validation_participant_id:
            raise ValueError("NMI validation is enabled, but no DNSPParticipantId was provided.")
        return self

    @cached_property
    def validator(self) -> NmiValidator:
        """Returns an NmiValidator instance configured for the specified participant ID.

        Raises:
            RuntimeError: If NMI validation is disabled via configuration.
        """
        if not self.nmi_validation_enabled or not self.nmi_validation_participant_id:
            raise RuntimeError("NMI validation is disabled or unconfigured.")

        return NmiValidator(
            participant_id=self.nmi_validation_participant_id,
        )


class AppSettings(CommonSettings):

    debug: bool = False
    docs_url: str = "/docs"
    openapi_prefix: str = ""
    openapi_url: str = "/openapi.json"
    redoc_url: str = "/redoc"
    title: str = "envoy"
    version: str = importlib.metadata.version("envoy")

    cert_header: str = "x-forwarded-client-cert"  # either client certificate in PEM format or the sha256 fingerprint

    allow_device_registration: bool = False  # True: LFDI auth will allow unknown certs to register single EndDevices

    nmi_validation: NmiValidationSettings = Field(default_factory=NmiValidationSettings)

    allow_nmi_updates: bool = DEFAULT_ALLOW_NMI_UPDATES
    exclude_endpoints: Optional[EndpointExclusionSet] = None

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
