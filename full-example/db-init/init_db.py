import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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

# Initialize data objects
now = datetime.now(tz=ZoneInfo("UTC"))
client_cert = Certificate(lfdi=lfdi, created=now, expiry=cert_expiry)
agg_null_aggregator = Aggregator(name="NULL AGGREGATOR", created_time=now, changed_time=now, aggregator_id=0)
agg_client_test = Aggregator(name="test", created_time=now, changed_time=now)


# Set up database engine and session maker
engine = create_async_engine(os.environ["DATABASE_URL"])
session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    async with session_maker() as session:
        new_entries = False

        agg_count = session.select(func.count()).select_from(Aggregator)

        session.select()

        # Add certificate if it doesn't already exist
        if client_cert.certificate_id is None:
            session.add(client_cert)
            new_entries = True

        # Add aggregator if it doesn't already exist
        if agg_client_test.aggregator_id is None:
            session.add(agg_client_test)
            new_entries = True

        # Commit new entries and create assignment
        if new_entries:
            await session.commit()
            assignment = AggregatorCertificateAssignment(
                certificate_id=client_cert.certificate_id, aggregator_id=agg_client_test.aggregator_id
            )
            session.add(assignment)
            await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
