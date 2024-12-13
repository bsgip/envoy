import asyncio
from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo

from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends
from envoy.server.model.aggregator import Aggregator, AggregatorCertificateAssignment
from envoy.server.model.base import Certificate



with open("/test_certs/testuser.crt", "r") as f:
    lfdi = LFDIAuthDepends.generate_lfdi_from_pem(f.read())

now = datetime.now(tz=ZoneInfo("UTC"))
client_cert = Certificate(
    lfdi=lfdi,
    created=now,
    expiry=now + timedelta(weeks=52)
)

agg = Aggregator(
    name="test",
    created_time=now,
    changed_time=now
)



engine = create_async_engine(os.environ["DATABASE_URL"])
seshmaker = sessionmaker(engine,  class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    async with seshmaker() as sesh:
        sesh.select(client_cert)
        sesh.select(agg)

        if agg.aggregator_id is no

        await sesh.commit()
        agg_to_cert = AggregatorCertificateAssignment(certificate_id=client_cert.certificate_id, aggregator_id=agg.aggregator_id)
        sesh.add(agg_to_cert)
        await sesh.commit()

if __name__=="__main__":
    asyncio.run(main())