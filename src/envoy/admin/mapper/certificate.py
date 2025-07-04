from typing import Iterable

from envoy_schema.admin.schema.certificate import (
    CertificateResponse,
    CertificatePageResponse,
    CertificateAssignmentRequest,
)

from envoy.server import model


class CertificateMapper:
    @staticmethod
    def map_to_response(certificate: model.Certificate) -> CertificateResponse:
        """Converts an internal Certificate model to the schema CertificateResponse"""

        return CertificateResponse(
            certificate_id=certificate.certificate_id,
            created=certificate.created,
            lfdi=certificate.lfdi,
            expiry=certificate.expiry,
        )

    @staticmethod
    def map_to_page_response(
        total_count: int, start: int, limit: int, certificates: Iterable[model.Certificate]
    ) -> CertificatePageResponse:
        """Converts a page of Certificate models to the schema CertificatePageResponse"""
        return CertificatePageResponse(
            total_count=total_count,
            start=start,
            limit=limit,
            certificates=[CertificateMapper.map_to_response(a) for a in certificates],
        )

    @staticmethod
    def map_from_many_request(certificates: Iterable[CertificateAssignmentRequest]) -> list[model.Certificate]:
        """Converts an iterable of CertificateAssignmentRequests into a list of sqlalchemy model certificates"""
        return [
            model.Certificate(
                certificate_id=c.certificate_id,
                lfdi=c.lfdi,
                expiry=c.expiry,
            )
            for c in certificates
        ]
