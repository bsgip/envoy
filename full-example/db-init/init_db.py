import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.model.aggregator import Aggregator, AggregatorCertificateAssignment
from envoy.server.model.base import Certificate

# Load certificate and extract expiry
CERT_PATH = "/test_certs/testclient.crt"
with open(CERT_PATH, "r") as cert_file:
    cert_pem = cert_file.read()
    cert = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
    cert_expiry = cert.not_valid_after

# Generate LFDI
lfdi = LFDIAuthDepends.generate_lfdi_from_pem(cert_pem)


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

            # Add our client aggregator and special "NULL" aggregator
            # NOTE - this will not increment the underlying sequences - should be fine for this demo example
            # but will cause issues if any code attempts to insert a new agg/certificate
            await session.execute(
                insert(Aggregator).values(name="NULL AGGREGATOR", created_time=now, changed_time=now, aggregator_id=0)
            )
            await session.execute(
                insert(Aggregator).values(name="Test", created_time=now, changed_time=now, aggregator_id=1)
            )
            await session.execute(
                insert(Certificate).values(lfdi=lfdi, created=now, expiry=cert_expiry, certificate_id=1)
            )
            await session.execute(insert(AggregatorCertificateAssignment).values(certificate_id=1, aggregator_id=1))
            await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
