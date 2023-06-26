import base64
import hashlib
import urllib.parse
from http import HTTPStatus

from fastapi import HTTPException, Request
from fastapi_async_sqlalchemy import db

from envoy.server.crud.auth import select_client_ids_using_lfdi


class LFDIAuthDepends:
    """Dependency class for generating the Long Form Device Identifier (LFDI) from a client TLS
    certificate in Privacy-Enhanced Mail (PEM) format. The client certificate is expected to be
    included in the request header by the TLS termination proxy.

    Definition of LFDI can be found in the IEEE Std 2030.5-2018 on page 40.
    """

    def __init__(self, cert_header: str):
        self.cert_header = cert_header.lower()  # fastapi will always return headers in lowercase form

    async def __call__(self, request: Request):
        if self.cert_header not in request.headers.keys():
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Missing certificate PEM header from gateway."
            )

        cert_fingerprint = request.headers[self.cert_header]

        # generate lfdi
        lfdi = LFDIAuthDepends.generate_lfdi_from_fingerprint(cert_fingerprint)

        async with db():
            client_ids = await select_client_ids_using_lfdi(lfdi, db.session)

        if not client_ids:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Unrecognised certificate ID.")

        request.state.certificate_id = client_ids.certificate_id
        request.state.aggregator_id = client_ids.aggregator_id

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
