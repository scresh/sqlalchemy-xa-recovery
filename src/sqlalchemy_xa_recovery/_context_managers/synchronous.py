"""Context manager for SQLAlchemy two-phase sessions."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager, suppress
from typing import Any

from sqlalchemy import Connection, Engine, TwoPhaseTransaction

from sqlalchemy_xa_recovery._context_managers._helpers import reverse_binds
from sqlalchemy_xa_recovery._session import (
    TwoPhaseSession,
    XAOutcomeUnknownError,
)
from sqlalchemy_xa_recovery._value_objects import Xid, XidBase, XidPrefix


@contextmanager
def two_phase_session(
    binds: dict[type[Any], Engine],
    xid_prefix: XidPrefix | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Generator[TwoPhaseSession]:
    """Create a session spanning multiple database engines with XA semantics."""
    xid_prefix: XidPrefix = xid_prefix or XidPrefix()
    reversed_binds = reverse_binds(binds)
    xid_base = XidBase(database_count=len(reversed_binds), prefix=xid_prefix)

    connection_binds: dict[type[Any], Connection] = {}
    ordered_transactions: list[TwoPhaseTransaction] = []
    ordered_connections: list[Connection] = []

    with ExitStack() as stack:
        for database_index, (engine, tables) in enumerate(reversed_binds.items()):
            xid = Xid(xid_base=xid_base, database_index=database_index)

            connection = stack.enter_context(engine.connect())
            ordered_connections.append(connection)

            transaction = connection.begin_twophase(xid.raw_value)
            ordered_transactions.append(transaction)

            connection_binds.update(dict.fromkeys(tables, connection))

        session = TwoPhaseSession(
            binds=connection_binds,
            ordered_transactions=ordered_transactions,
            **kwargs,
        )
        stack.enter_context(session)

        try:
            yield session
        except XAOutcomeUnknownError:
            for transaction in ordered_transactions:
                with suppress(Exception):
                    transaction.connection.invalidate()
            raise
        except BaseException:
            session.rollback()
            raise

        if not session.xa_completed:
            session.rollback()
