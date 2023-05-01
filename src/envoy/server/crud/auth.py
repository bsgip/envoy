from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from envoy.server.model import AggregatorCertificateAssignment, Certificate


@dataclass
class ClientIdDetails:
    certificate_id: int
    aggregator_id: int


async def select_client_ids_using_lfdi(
    lfdi: str, session: AsyncSession
) -> Optional[ClientIdDetails]:
    """Query to retrieve certificate and aggregator IDs, if existing.
    NB. Assumption is that only aggregator clients are allowed to communicate with envoy.

    Expired certificates will NOT be returned by this function
    """
    stmt = (
        select(
            Certificate.certificate_id,
            AggregatorCertificateAssignment.aggregator_id
        )
        .join(
            AggregatorCertificateAssignment,
            Certificate.certificate_id == AggregatorCertificateAssignment.certificate_id,
        )
        .where(Certificate.lfdi == lfdi)
        .where(Certificate.expiry > func.now())  # Only want unexpired certs
    )

    resp = await session.execute(stmt)

    mapping = resp.mappings().one_or_none()
    if not mapping:
        return None

    return ClientIdDetails(certificate_id=mapping["certificate_id"], aggregator_id=mapping["aggregator_id"])
