import base64
import hashlib
import urllib.parse

from fastapi import HTTPException, Request

from server.crud import auth
from fastapi_async_sqlalchemy import db


class LFDIAuthDepends:
    """Depedency class for generating the Long Form Device Identifier (LFDI) from a client TLS
    certificate in Privacy-Enhanced Mail (PEM) format. The client certificate is expected to be
    included in the request header by the TLS termination proxy.

    Definition of LFDI can be found in the IEEE Std 2030.5-2018 on page 40.
    """

    def __init__(self, cert_pem_header: str):
        self.cert_pem_header = cert_pem_header

    async def __call__(self, request: Request) -> int:
        if self.cert_pem_header not in request.headers.keys():
            raise HTTPException(
                status_code=500, detail="Missing certificate PEM header from gateway."
            )  # Malformed

        cert_fingerprint = request.headers[self.cert_pem_header]

        # generate lfdi
        lfdi = self.generate_lfdi_from_pem(cert_fingerprint)

        cert_id = await auth.select_certificate_id_using_lfdi(lfdi, db.session)

        if not cert_id:
            raise HTTPException(
                status_code=403, detail="Unrecognised certificate ID."
            )  # Forbidden

        request.state.cert_id = cert_id

    def generate_lfdi_from_pem(self, cert_pem: str) -> str:
        """This function generates the 2030.5-2018 lFDI (Long-form device identifier) from the device's
        TLS certificate in pem (Privacy Enhanced Mail) format, i.e. Base64 encoded DER
        (Distinguished Encoding Rules) certificate, as decribed in Section 6.3.4
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
        return self._cert_fingerprint_to_lfdi(
            self._cert_pem_to_cert_fingerprint(cert_pem)
        )

    @staticmethod
    def _cert_fingerprint_to_lfdi(cert_fingerprint: str) -> str:
        return cert_fingerprint[:42]

    @staticmethod
    def _cert_pem_to_cert_fingerprint(cert_pem: str) -> str:
        # URL/percent decode
        cert_pem = urllib.parse.unquote(cert_pem)

        # remove header/footer
        cert_pem = "\n".join(cert_pem.splitlines()[1:-1])

        # decode base64
        cert_pem = base64.b64decode(cert_pem)

        # sha256 hash
        hashing_obj = hashlib.sha256(cert_pem)
        return hashing_obj.hexdigest()
