import base64
import hashlib
import logging
import urllib.parse
import re
from http import HTTPStatus
from typing import Any, Optional
from cryptography.x509 import load_pem_x509_certificate

from fastapi import Request
from fastapi_async_sqlalchemy import db

from envoy.server.api.error_handler import LoggedHttpException
from envoy.server.cache import AsyncCache, ExpiringValue
from envoy.server.crud.auth import ClientIdDetails, select_all_client_id_details
from envoy.server.crud.common import convert_lfdi_to_sfdi
from envoy.server.crud.end_device import select_single_site_with_sfdi
from envoy.server.model.aggregator import NULL_AGGREGATOR_ID
from envoy.server.request_scope import CertificateType

logger = logging.getLogger(__name__)


def is_valid_base64_in_pem(pem_str: str) -> bool:
    """
    Various checks for PEM format validity.

    1. Properly formatted with BEGIN/END markers.
    2. Uses base64 encoding
    3. Can be loaded by cryptography.x509.load_pem_x509_certificate
    """

    pem_str = urllib.parse.unquote(pem_str)
    match = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", pem_str, re.DOTALL)
    if not match:
        return False

    base64_content = "".join(match.group(1).split())
    try:
        load_pem_x509_certificate(pem_str.encode("utf-8"))
        base64.b64decode(base64_content, validate=True)
    except Exception:
        return False

    return True


async def update_client_id_details_cache(_: Any) -> dict[str, ExpiringValue[ClientIdDetails]]:
    """To be called on cache miss. Updates the entire clientIdDetails cache with active (non-expired) client details
    from the Certificate and AggregatorCertificateAssignment tables.
    """

    # We create a fresh session here to ensure that anything fetched from the DB does NOT pollute the
    # session used by the rest of the request - This is out of an abundance of paranoia
    async with db():
        # This will include expired certs
        client_ids = await select_all_client_id_details(db.session)
    return {cid.lfdi: ExpiringValue(expiry=cid.expiry, value=cid) for cid in client_ids}


class LFDIAuthDepends:
    """Dependency class for generating the Long Form Device Identifier (LFDI) from a client TLS
    certificate in Privacy-Enhanced Mail (PEM) format. The client certificate is expected to be
    included in the request header by the TLS termination proxy.

    Definition of LFDI can be found in the IEEE Std 2030.5-2018 on page 40.

    This auth can be configured to receive EITHER a full client cert PEM or just the sha256 fingerprint
    """

    cert_header: str
    allow_device_registration: bool
    aggregator_cert_cache: AsyncCache[str, ClientIdDetails]

    def __init__(self, cert_header: str, allow_device_registration: bool):
        # fastapi will always return headers in lowercase form
        self.cert_header = cert_header.lower()
        self.allow_device_registration = allow_device_registration
        self.aggregator_cert_cache = AsyncCache(update_fn=update_client_id_details_cache)

    async def __call__(self, request: Request) -> None:
        # Try extracting the lfdi from either the PEM if we receive it directly or the fingerprint if we get that
        cert_header_val = request.headers.get(self.cert_header, None)
        if not cert_header_val:
            raise LoggedHttpException(
                logger,
                exc=None,
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Missing certificate PEM header/fingerprint from gateway.",
            )

        if cert_header_val.startswith("-----BEGIN"):
            if not is_valid_base64_in_pem(cert_header_val):
                raise LoggedHttpException(
                    logger,
                    exc=None,
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="Invalid certificate PEM format.",
                )
            lfdi = LFDIAuthDepends.generate_lfdi_from_pem(cert_header_val)
        else:
            lfdi = LFDIAuthDepends.generate_lfdi_from_fingerprint(cert_header_val)

        try:
            sfdi = convert_lfdi_to_sfdi(lfdi)
        except Exception as exc:
            raise LoggedHttpException(
                logger, exc=exc, status_code=HTTPStatus.BAD_REQUEST, detail="Unrecognised client certificate."
            )

        # get client id details from cache, will return None if expired or never existed.
        expirable_client_id = await self.aggregator_cert_cache.get_value_ignore_expiry(None, lfdi)
        site_id: Optional[int] = None
        aggregator_id: Optional[int] = None
        if expirable_client_id:
            # We have identified that this certificate lives in the certificate table and is therefore
            # an aggregator cert (expired or not)
            if expirable_client_id.is_expired():
                raise LoggedHttpException(
                    logger,
                    exc=None,
                    status_code=HTTPStatus.FORBIDDEN,
                    detail=f"Client certificate {lfdi} is marked as expired by the server.",
                )
            aggregator_id = expirable_client_id.value.aggregator_id
            source = CertificateType.AGGREGATOR_CERTIFICATE
        else:
            # It's not an aggregator cert:
            # The cert has passed our TLS termination so its signing chain is valid - the only question
            # is whether this server is setup to allow single device registration or whether all requests must
            # be routed through an aggregator (and their client cert)
            if self.allow_device_registration:
                source = CertificateType.DEVICE_CERTIFICATE
                async with db():
                    site = await select_single_site_with_sfdi(db.session, sfdi=sfdi, aggregator_id=NULL_AGGREGATOR_ID)
                    if site is not None:
                        site_id = site.site_id
            else:
                # Reject the attempted device cert request
                raise LoggedHttpException(
                    logger, exc=None, status_code=HTTPStatus.FORBIDDEN, detail="Unrecognised client certificate."
                )

        request.state.source = source
        request.state.lfdi = lfdi
        request.state.sfdi = sfdi

        request.state.aggregator_id = aggregator_id
        request.state.site_id = site_id

    @staticmethod
    def generate_lfdi_from_pem(cert_pem: str) -> str:
        """This function generates the sep2 / 2030.5-2018 lFDI (Long-form device identifier) from the device's
        TLS certificate in pem (Privacy Enhanced Mail) format, i.e. Base64 encoded DER
        (Distinguished Encoding Rules) certificate, as described in Section 6.3.4
        of IEEE Std 2030.5-2018.

        The lFDI is derived, from the certificate in PEM format, according to the following steps:
            1- Base64 decode the PEM to DER.
            2- Performing SHA256 hash on the DER to generate the certificate fingerprint.
            3- Left truncating the certificate fingerprint to 160 bits.

        Args:
            cert_pem: TLS certificate in PEM format.

        Return:
            The lFDI as a hex string.
        """
        # generate lfdi
        return LFDIAuthDepends.generate_lfdi_from_fingerprint(LFDIAuthDepends._cert_pem_to_cert_fingerprint(cert_pem))

    @staticmethod
    def generate_lfdi_from_fingerprint(cert_fingerprint: str) -> str:
        """This function generates the sep2 / 2030.5-2018 lFDI (Long-form device identifier) from the device's
        TLS certificate fingerprint (40 hex chars), as described in Section 6.3.4
        of IEEE Std 2030.5-2018 which states The LFDI SHALL be the certificate fingerprint left-truncated to
        160 bits (20 octets).

        Args:
            cert_pem: TLS certificate in PEM format.

        Return:
            The lFDI as a hex string.
        """
        # generate lfdi
        return cert_fingerprint[:40]

    @staticmethod
    def _cert_pem_to_cert_fingerprint(cert_pem_b64: str) -> str:
        """The certificate fingerprint is the result of performing a SHA256 operation over the whole DER-encoded
        certificate and is used to derive the SFDI and LFDI"""
        # Replace %xx escapes with their single-character equivalent
        cert_pem_b64 = urllib.parse.unquote(cert_pem_b64)

        # remove header/footer
        cert_pem_b64 = "\n".join(cert_pem_b64.splitlines()[1:-1])

        # decode base64
        cert_pem_bytes = base64.b64decode(cert_pem_b64)

        # sha256 hash
        hashing_obj = hashlib.sha256(cert_pem_bytes)
        return hashing_obj.hexdigest()
