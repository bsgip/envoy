from typing import AsyncGenerator

from envoy.notification.handler import generate_broker
from envoy.notification.settings import generate_settings

settings = generate_settings()


async def session_dependency() -> AsyncGenerator[AsyncSession, None]:
    print("Startup")
    await asyncio.sleep(0.1)

    yield "value"

    await asyncio.sleep(0.1)
    print("Shutdown")


broker = generate_broker(settings.rabbit_mq_broker_url)
