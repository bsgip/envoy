from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from envoy.server.model import AggregatorCertificateAssignment, Certificate


@dataclass(frozen=True)
class ClientIdDetails:
    lfdi: str
    aggregator_id: int
    expiry: datetime


async def select_all_client_id_details(session: AsyncSession) -> list[ClientIdDetails]:
    """Query to retrieve all client id details sourced from the 'certificate' and
    'aggregator_certificate_assignment' tables.
    NB. Assumption is that only aggregator clients are allowed to communicate with envoy.

    Expired certificates will NOT be returned by this function
    """
    stmt = (
        select(
            Certificate.lfdi,
            AggregatorCertificateAssignment.aggregator_id,
            Certificate.expiry,
        )
        .join(
            AggregatorCertificateAssignment,
            Certificate.certificate_id == AggregatorCertificateAssignment.certificate_id,
        )  # Inner join implies that aggregator certs will be returned
        .where(Certificate.expiry > func.now())  # Only want unexpired certs
    )

    resp = await session.execute(stmt)

    mapping = resp.mappings().all()
    return [ClientIdDetails(**cid) for cid in mapping]
