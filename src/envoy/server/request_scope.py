from dataclasses import dataclass
from enum import IntEnum, auto
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException

from envoy.server.crud.site import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID


class CertificateType(IntEnum):
    """The different types of incoming certificates"""

    # Represents the ability to create/manage multiple EndDevices under a specified Aggregator
    # These devices will be decoupled from the LFDI of the certificate
    AGGREGATOR_CERTIFICATE = auto()

    # Represents the ability to create/manage a SINGLE EndDevice that will be stored under the "NULL Aggregator"
    # This device will have the LFDI/SFDI match the certificate lfdi/sfdi
    DEVICE_CERTIFICATE = auto()


@dataclass(frozen=True)
class BaseRequestScope:
    """The common fields for ALL request scopes. A request scope is a narrowed form of auth that outline very
    precise restrictions on what a request can interact with. A scope is created from a RawRequestClaims."""

    lfdi: str  # The lowercase lfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    sfdi: int  # The sfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    href_prefix: Optional[str]  # If set - all outgoing href's should be prefixed with this value
    iana_pen: int  # The IANA Private Enterprise Number of the org hosting this utility server instance


@dataclass(frozen=True)
class RawRequestClaims:
    """The raw auth claims which has been extracted from the incoming request and validated by the middleware. Claims
    represent the range of all possible authorisation interactions with the server based on the supplied credentials.

    If:
    aggregator_id_scope is None and site_id_scope is None:
        This request has NO access to anything beyond registering a new edev
    aggregator_id_scope is None and site_id_scope is not None:
        This request cannot access ANY aggregator resources - the only thing it can access is that site_id_scope
    aggregator_id_scope is not None and site_id_scope is None:
        This request can access anything under aggregator_id_scope
    aggregator_id_scope is not None and site_id_scope is not None:
        This is an unsupported case and will raise a ValueError
    """

    source: CertificateType  # How would we classify the the certificate that generated these claims?

    lfdi: str  # The lfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    sfdi: int  # The sfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    href_prefix: Optional[str]  # If set - all outgoing href's should be prefixed with this value
    iana_pen: int  # The IANA Private Enterprise Number of the org hosting this utility server instance

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    # This can be None if the request does not have access to any aggregator (NOT unscoped access)
    aggregator_id_scope: Optional[int]
    # The site id that a request is scoped to (sourced from auth dependencies)
    # This can be None if the request does not have a single site scope
    site_id_scope: Optional[int]

    def to_unregistered_request_scope(self) -> "UnregisteredRequestScope":
        """Attempt to convert these raw claims into a UnregisteredRequestScope, raising a HTTPException if not
        possible"""
        if self.source == CertificateType.DEVICE_CERTIFICATE and self.aggregator_id_scope is not None:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"{self.lfdi} is improperly scoped to aggregator '{self.aggregator_id_scope}'.",
            )

        return UnregisteredRequestScope(
            lfdi=self.lfdi,
            sfdi=self.sfdi,
            href_prefix=self.href_prefix,
            iana_pen=self.iana_pen,
            source=self.source,
            aggregator_id=self.aggregator_id_scope if self.aggregator_id_scope is not None else NULL_AGGREGATOR_ID,
        )

    def to_mup_list_request_scope(self) -> "MUPListRequestScope":
        """Attempt to convert these raw claims into a MUPListRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException"""
        if self.source == CertificateType.DEVICE_CERTIFICATE and self.aggregator_id_scope is not None:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"{self.lfdi} is improperly scoped to aggregator '{self.aggregator_id_scope}'.",
            )

        return MUPListRequestScope(
            lfdi=self.lfdi,
            sfdi=self.sfdi,
            href_prefix=self.href_prefix,
            iana_pen=self.iana_pen,
            source=self.source,
            aggregator_id=self.aggregator_id_scope if self.aggregator_id_scope is not None else NULL_AGGREGATOR_ID,
            device_site_id=self.site_id_scope,
        )

    def to_mup_request_scope(self) -> "MUPRequestScope":
        """Attempt to convert these raw claims into a MUPRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException"""
        base_scope: DeviceOrAggregatorRequestScope
        if self.source == CertificateType.AGGREGATOR_CERTIFICATE:
            base_scope = self.to_device_or_aggregator_request_scope(requested_site_id=None)
        elif self.source == CertificateType.DEVICE_CERTIFICATE:
            base_scope = self.to_device_or_aggregator_request_scope(requested_site_id=self.site_id_scope)
        else:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"{self.lfdi} has an unrecognised certificate source '{self.source}'.",
            )

        return MUPRequestScope(
            lfdi=base_scope.lfdi,
            sfdi=base_scope.sfdi,
            href_prefix=base_scope.href_prefix,
            iana_pen=base_scope.iana_pen,
            source=base_scope.source,
            aggregator_id=base_scope.aggregator_id,
            display_site_id=base_scope.display_site_id,
            site_id=base_scope.site_id,
        )

    def to_device_or_aggregator_request_scope(
        self, requested_site_id: Optional[int]
    ) -> "DeviceOrAggregatorRequestScope":
        """Attempt to convert these raw claims into a DeviceOrAggregatorRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException

        requested_site_id: If None - no site_id filter, otherwise the request is scoped to this specific site_id
        """
        agg_id = self.aggregator_id_scope
        if agg_id is None:
            if self.site_id_scope is None:
                # Client has no auth yet (likely a device cert (non aggregator) that hasn't been registered yet)
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail=f"{self.lfdi} is not scoped to access this resource (has an EndDevice been registered?)",
                )
            agg_id = NULL_AGGREGATOR_ID

        if requested_site_id == VIRTUAL_END_DEVICE_SITE_ID:
            # The virtual aggregator end device is shorthand for no site scope
            requested_site_id = None
        display_site_id = requested_site_id if requested_site_id is not None else VIRTUAL_END_DEVICE_SITE_ID

        if self.site_id_scope is not None and requested_site_id != self.site_id_scope:
            # Client is restricted to a specific site and they are trying to access broader than that
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Client {self.lfdi} is scoped to EndDevice {self.site_id_scope}",
            )

        return DeviceOrAggregatorRequestScope(
            lfdi=self.lfdi,
            sfdi=self.sfdi,
            href_prefix=self.href_prefix,
            iana_pen=self.iana_pen,
            source=self.source,
            aggregator_id=agg_id,
            display_site_id=display_site_id,
            site_id=requested_site_id,
        )

    def to_aggregator_request_scope(self, requested_site_id: Optional[int]) -> "AggregatorRequestScope":
        """Attempt to convert these raw claims into an AggregatorRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException

        requested_site_id: If None - no site_id filter, otherwise the request is scoped to this specific site_id"""
        scope = self.to_device_or_aggregator_request_scope(requested_site_id)
        if scope.aggregator_id == NULL_AGGREGATOR_ID:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=f"Client {self.lfdi} doesn't have access to this resource"
            )
        return AggregatorRequestScope(
            lfdi=scope.lfdi,
            sfdi=scope.sfdi,
            href_prefix=scope.href_prefix,
            iana_pen=scope.iana_pen,
            source=self.source,
            aggregator_id=scope.aggregator_id,
            display_site_id=scope.display_site_id,
            site_id=scope.site_id,
        )

    def to_site_request_scope(self, requested_site_id: int) -> "SiteRequestScope":
        """Attempt to convert these raw claims into a SiteRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException

        requested_site_id: The request is scoped to this specific site_id
        """
        agg_id = self.aggregator_id_scope
        if agg_id is None:
            if self.site_id_scope is None:
                # Client has no auth yet (likely a device cert (non aggregator) that hasn't been registered yet)
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail=f"{self.lfdi} is not scoped to access this resource (has an EndDevice been registered?)",
                )
            agg_id = NULL_AGGREGATOR_ID

        if requested_site_id == VIRTUAL_END_DEVICE_SITE_ID:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Client {self.lfdi} can't access this resource for the aggregator EndDevice",
            )

        if self.site_id_scope is not None and requested_site_id != self.site_id_scope:
            # Client is restricted to a specific site and they are trying to access broader than that
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Client {self.lfdi} is scoped to EndDevice {self.site_id_scope}",
            )

        return SiteRequestScope(
            lfdi=self.lfdi,
            sfdi=self.sfdi,
            href_prefix=self.href_prefix,
            iana_pen=self.iana_pen,
            source=self.source,
            aggregator_id=agg_id,
            display_site_id=requested_site_id,
            site_id=requested_site_id,
        )


@dataclass(frozen=True)
class DeviceOrAggregatorRequestScope(BaseRequestScope):
    """A refined version of RawRequestScope to indicate that a request is scoped to access EITHER:

    All sites underneath a specific aggregator ID (but never all sites under the NULL_AGGREGATOR_ID)
    OR
    A single site underneath a specific aggregator ID

    This should support the following usecases:
        Aggregator cert accessing the aggregator EndDevice
        Aggregator cert accessing a EndDevice assigned to that aggregator
        Device cert accessing the already registered EndDevice associated with the device cert
    """

    source: CertificateType  # What created this certificate?

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    aggregator_id: int

    # This is essentially an echo of the site_id that was queried by the client. It'll be VIRTUAL_END_DEVICE_SITE_ID
    # if site_id is None. This should be used for generating site_id's in response hrefs
    display_site_id: int

    # If specified - What specific site_id is this request scoped to (otherwise no site scope)
    site_id: Optional[int]


@dataclass(frozen=True)
class MUPListRequestScope(BaseRequestScope):
    """This is a unique scope that allows for accessing the MirrorUsagePoint list resource. It allows any combination
    of aggregator / device certificates irrespective of their current EndDevice registration status. This should NOT
    be used outside of the MUPListResource as it's a pretty wide open scope.

    This should support the following usecases:
        Aggregator cert accessing the MUP List
        Device cert accessing the MUP list (when registered)
        Device cert accessing the MUP list (when not registered)
    """

    source: CertificateType  # What created this certificate?

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    aggregator_id: int

    # If specified - What specific site_id is this request scoped to. This is only applicable to device certificates
    # This can be None for a device certificate indicating that NO EndDevice has been registered.
    device_site_id: Optional[int]


@dataclass(frozen=True)
class MUPRequestScope(DeviceOrAggregatorRequestScope):
    """Similar to DeviceOrAggregatorRequestScope but removes support for Aggregators requesting a specific site.
    It's basically a DeviceOrAggregatorRequestScope that hasn't been forcibly constrained to a single site

    This should support the following usecases:
        Aggregator cert accessing the aggregator EndDevice
        Device cert accessing the already registered EndDevice associated with the device cert
    """

    pass


@dataclass(frozen=True)
class SiteRequestScope(DeviceOrAggregatorRequestScope):
    """Similar to DeviceOrAggregatorRequestScope but narrowed to a SINGLE site (redefining site_id to be mandatory).

    This should support the following usecases:
        Aggregator cert accessing a EndDevice assigned to that aggregator
        Device cert accessing the already registered EndDevice associated with the device cert
    """

    # What specific site_id is this request scoped to
    site_id: int


@dataclass(frozen=True)
class AggregatorRequestScope(BaseRequestScope):
    """Similar to DeviceOrAggregatorRequestScope but ALSO guarantees that aggregator_id will NEVER be
    NULL_AGGREGATOR_ID which eliminates any possibility of a Device certificate using this scope.

    This should support the following usecases:
        Aggregator cert accessing the aggregator EndDevice
        Aggregator cert accessing a EndDevice assigned to that aggregator
    """

    source: CertificateType  # What created this certificate?

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    aggregator_id: int

    # This is essentially an echo of the site_id that was queried by the client. It'll be VIRTUAL_END_DEVICE_SITE_ID
    # if site_id is None. This should be used for generating site_id's in response hrefs
    display_site_id: int

    # If specified - What specific site_id is this request scoped to (otherwise no site scope)
    site_id: Optional[int]


@dataclass(frozen=True)
class UnregisteredRequestScope(BaseRequestScope):
    """Supports a pretty broad set of possibilities for accepting a client cert of any type.

    This should support the following usecases:
        Aggregator cert accessing the aggregator EndDevice
        Aggregator cert accessing a EndDevice assigned to that aggregator
        Device cert accessing the already registered EndDevice associated with the device cert
        Device cert that doesn't have a registered EndDevice
    """

    source: CertificateType  # What created this certificate?

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    # In the event of a device certificate source - this will be the NULL_AGGREGATOR_ID
    aggregator_id: int
