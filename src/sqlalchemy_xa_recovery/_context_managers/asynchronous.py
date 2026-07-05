from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from typing import Any

from sqlalchemy import TwoPhaseTransaction
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from sqlalchemy_xa_recovery._context_managers._helpers import begin_twophase, reverse_binds
from sqlalchemy_xa_recovery._session import AsyncTwoPhaseSession, XAOutcomeUnknownError
from sqlalchemy_xa_recovery._value_objects import Xid, XidBase, XidPrefix


@asynccontextmanager
async def async_two_phase_session(
    binds: dict[type[Any], AsyncEngine],
    xid_prefix: XidPrefix | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> AsyncGenerator[AsyncTwoPhaseSession]:
    """Create an async session spanning multiple database engines with XA semantics."""
    xid_prefix: XidPrefix = xid_prefix or XidPrefix()
    reversed_binds = reverse_binds(binds)
    xid_base = XidBase(database_count=len(reversed_binds), prefix=xid_prefix)

    connection_binds: dict[type[Any], AsyncConnection] = {}
    ordered_transactions: list[TwoPhaseTransaction] = []
    ordered_connections: list[AsyncConnection] = []

    async with AsyncExitStack() as stack:
        for database_index, (engine, tables) in enumerate(reversed_binds.items()):
            xid = Xid(xid_base=xid_base, database_index=database_index)

            connection = await stack.enter_async_context(engine.connect())
            ordered_connections.append(connection)

            transaction = await connection.run_sync(begin_twophase, xid.raw_value)
            ordered_transactions.append(transaction)

            connection_binds.update(dict.fromkeys(tables, connection))

        session = AsyncTwoPhaseSession(
            binds=connection_binds,
            ordered_transactions=ordered_transactions,
            **kwargs,
        )
        await stack.enter_async_context(session)

        try:
            yield session
        except XAOutcomeUnknownError:
            for connection in ordered_connections:
                with suppress(Exception):
                    await connection.invalidate()
            raise
        except BaseException:
            await session.rollback()
            raise

        if not session.xa_completed:
            await session.rollback()
