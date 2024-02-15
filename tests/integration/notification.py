from typing import Optional

from psycopg import Connection
from taskiq import BrokerMessage, InMemoryBroker

from envoy.notification.handler import STATE_DB_SESSION_MAKER, STATE_HREF_PREFIX
from tests.postgres_testing import SingleAsyncEngineState


class TestableBroker(InMemoryBroker):
    """
    This broker extends InMemoryBroker but also injects all state variables required by "normal running" taskiq workers
    """

    db_conn: Connection
    href_prefix: Optional[str]
    engine_state: Optional[SingleAsyncEngineState]

    def __init__(self, db_conn: Connection, href_prefix: Optional[str]) -> None:
        super().__init__(sync_tasks_pool_size=1, max_async_tasks=5)
        self.db_conn = db_conn
        self.href_prefix = href_prefix

    async def startup(self) -> None:
        """Setup broker state for our test environment"""
        await super().startup()

        self.engine_state = SingleAsyncEngineState(self.db_conn)

        setattr(self.state, STATE_DB_SESSION_MAKER, self.engine_state.session_maker)
        setattr(self.state, STATE_HREF_PREFIX, self.href_prefix)

    async def shutdown(self) -> None:
        """Cleanup broker state for our test environment"""
        await super().shutdown()

        setattr(self.state, STATE_DB_SESSION_MAKER, None)
        setattr(self.state, STATE_HREF_PREFIX, None)

        if self.engine_state:
            await self.engine_state.dispose()
            self.engine_state = None

    async def kick(self, message: BrokerMessage) -> None:
        await super().kick(message)
