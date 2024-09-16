from dataclasses import dataclass
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException

from envoy.server.crud.end_device import VIRTUAL_END_DEVICE_SITE_ID
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID


@dataclass(frozen=True)
class BaseRequestScope:
    """The common fields for ALL request scopes"""

    lfdi: str  # The lfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    sfdi: int  # The sfdi associated with the aggregator/site ID (sourced from the client TLS certificate)
    href_prefix: Optional[str]  # If set - all outgoing href's should be prefixed with this value


@dataclass(frozen=True)
class RawRequestClaims(BaseRequestScope):
    """The raw auth claims which has been extracted from the incoming request

    If:
    aggregator_id is None and site_id is None:
        This request has NO access to anything beyond registering a new edev
    aggregator_id is None and site_id is not None:
        This request cannot access ANY aggregator resources - the only thing it can access is that site_id
    aggregator_id is not None and site_id is None:
        This request can access anything under aggregator_id
    aggregator_id is not None and site_id is not None:
        This is an unsupported case and will raise a ValueError
    """

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    # This can be None if the request does not have access to any aggregator (NOT unscoped access)
    aggregator_id: Optional[int]
    # The site id that a request is scoped to (sourced from auth dependencies)
    # This can be None if the request does not have a single site scope
    site_id: Optional[int]

    def to_aggregator_request_scope(self, requested_site_id: Optional[int]) -> "AggregatorRequestScope":
        """Attempt to convert this raw scope into an AggregatorRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException

        requested_site_id: If None - no site_id filter, otherwise the request is scoped to this specific site_id
        """
        agg_id = self.aggregator_id
        if agg_id is None:
            if self.site_id is None:
                # Client has no auth yet (likely a device cert (non aggregator) that hasn't been registered yet)
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail=f"Client {self.lfdi} is not scoped to access this resource (has an EndDevice been registered?)",
                )
            agg_id = NULL_AGGREGATOR_ID

        if requested_site_id == VIRTUAL_END_DEVICE_SITE_ID:
            # The virtual aggregator end device is shorthand for no site scope
            requested_site_id = None
        display_site_id = requested_site_id if requested_site_id is not None else VIRTUAL_END_DEVICE_SITE_ID

        if self.site_id is not None and requested_site_id != self.site_id:
            # Client is restricted to a specific site and they are trying to access broader than that
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=f"Client {self.lfdi} is scoped to EndDevice {self.site_id}"
            )

        return AggregatorRequestScope(
            lfdi=self.lfdi,
            sfdi=self.sfdi,
            href_prefix=self.href_prefix,
            aggregator_id=agg_id,
            display_site_id=display_site_id,
            site_id=requested_site_id,
        )

    def to_site_request_scope(self, requested_site_id: int) -> "SiteRequestScope":
        """Attempt to convert this raw scope into a SiteRequestScope. If the request doesn't match the
        client credentials, this will raise a HTTPException

        requested_site_id: The request is scoped to this specific site_id
        """
        agg_id = self.aggregator_id
        if agg_id is None:
            if self.site_id is None:
                # Client has no auth yet (likely a device cert (non aggregator) that hasn't been registered yet)
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail=f"Client {self.lfdi} is not scoped to access this resource (has an EndDevice been registered?)",
                )
            agg_id = NULL_AGGREGATOR_ID

        if requested_site_id == VIRTUAL_END_DEVICE_SITE_ID:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Client {self.lfdi} can't access this resource for the aggregator EndDevice",
            )

        if self.site_id is not None and requested_site_id != self.site_id:
            # Client is restricted to a specific site and they are trying to access broader than that
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=f"Client {self.lfdi} is scoped to EndDevice {self.site_id}"
            )

        return SiteRequestScope(
            lfdi=self.lfdi,
            sfdi=self.sfdi,
            href_prefix=self.href_prefix,
            aggregator_id=agg_id,
            display_site_id=requested_site_id,
            site_id=requested_site_id,
        )


@dataclass(frozen=True)
class AggregatorRequestScope(BaseRequestScope):
    """A refined version of RawRequestScope to indicate that a request is scoped to access EITHER:

    All sites underneath a specific aggregator ID
    OR
    A single site underneath a specific aggregator ID
    """

    # The aggregator id that a request is scoped to (sourced from auth dependencies)
    aggregator_id: int

    # This is essentially an echo of the site_id that was queried by the client. It'll be VIRTUAL_END_DEVICE_SITE_ID
    # if site_id is None. This should be used for generating site_id's in response hrefs
    display_site_id: int

    # If specified - What specific site_id is this request scoped to (otherwise no site scope)
    site_id: Optional[int]


@dataclass(frozen=True)
class SiteRequestScope(AggregatorRequestScope):
    """Similar to AggregatorRequestScope but narrowed to a SINGLE site (i.e redefining site_id to be mandatory)"""

    # What specific site_id is this request scoped to
    site_id: int
