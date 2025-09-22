import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.model.aggregator import Aggregator, AggregatorCertificateAssignment, AggregatorDomain
from envoy.server.model.base import Certificate
from envoy.server.model.doe import SiteControlGroup


# There are two types of clients: aggregators and devices
# Aggregators have their certificates recorded in public.certificate
# while devices do not - envoy does not keep a record of non-aggregator
# device certificates.
AGG_CERT_PATH = os.environ.get("AGG_CERT_PATH", "/test_certs/testaggregator.crt")  # Aggregator Client


def load_cert(cert_path: str, now: datetime) -> Certificate:
    """Load certs, extract expiry and lfdi"""
    with open(cert_path, "r") as cert_file:
        cert_pem = cert_file.read()
        cert = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
        cert_expiry = cert.not_valid_after_utc
    # Generate LFDI
    lfdi = LFDIAuthDepends.generate_lfdi_from_pem(cert_pem)
    return Certificate(lfdi=lfdi, created=now, expiry=cert_expiry)


# Set up database engine and session maker
engine = create_async_engine(os.environ["DATABASE_URL"])
session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Run init code within a session
async def main() -> None:
    async with session_maker() as session:
        # If the aggregator table is empty - there is nothing in the DB - time to populate it
        agg_count = (await session.execute(select(func.count()).select_from(Aggregator))).scalar_one()
        if agg_count == 0:
            now = datetime.now(tz=ZoneInfo("UTC"))

            # load aggregator cert only
            agg_cert = load_cert(AGG_CERT_PATH, now)

            # add client aggregator
            agg = Aggregator(name="Test", created_time=now, changed_time=now)
            domain = AggregatorDomain(domain="example.com", created_time=now, changed_time=now)
            agg.domains = [domain]

            # Add our client aggregator and special "NULL" aggregator (used for device clients) - the NULL aggregator
            # should not be linked to any certificates.
            session.add(agg)
            session.add(agg_cert)

            await session.execute(
                insert(Aggregator).values(name="NULL AGGREGATOR", created_time=now, changed_time=now, aggregator_id=0)
            )
            await session.flush()

            session.add(
                AggregatorCertificateAssignment(certificate_id=agg_cert.certificate_id, aggregator_id=agg.aggregator_id)
            )

            site_control_group = SiteControlGroup(
                description="Default control group", primacy=1, fsa_id=1, created_time=now, changed_time=now
            )
            session.add(site_control_group)

            await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
