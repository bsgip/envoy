from contextlib import AsyncExitStack, _AsyncGeneratorContextManager, asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from fastapi import FastAPI


def generate_combined_lifespan_manager(
    managers: list[Callable[[FastAPI], _AsyncGeneratorContextManager]],
) -> Optional[Callable[[FastAPI], _AsyncGeneratorContextManager]]:
    """Given a (possibly empty) set of lifespan managers - create a single
    lifespan manager that will enter/exit them all sequentially

    Returns None if there are no managers supplied"""
    if not managers or len(managers) == 0:
        return None

    @asynccontextmanager
    async def combined_context_manager(app: FastAPI) -> AsyncIterator:
        """This context manager will run all the supplied managers"""

        async with AsyncExitStack() as exit_stack:
            state: Optional[dict[str, Any]] = None

            for manager in managers:
                sub_state = await exit_stack.enter_async_context(manager(app))

                if sub_state:
                    if state is None:
                        state = {}
                    state.update(sub_state)

            yield state

    return combined_context_manager
