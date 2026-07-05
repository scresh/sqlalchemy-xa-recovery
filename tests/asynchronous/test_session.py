from contextlib import AsyncExitStack
from typing import Any
from unittest.mock import create_autospec

import pytest
from sqlalchemy import Connection, TwoPhaseTransaction
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncConnection
from support.helpers import Database, async_create_wallet
from support.orm import ORM

from sqlalchemy_xa_recovery import AsyncTwoPhaseSession
from sqlalchemy_xa_recovery._value_objects import Xid, XidBase


@pytest.mark.asyncio
async def test_two_phase_session_requires_at_least_one_bind() -> None:
    with pytest.raises(InvalidRequestError) as exc_info:
        AsyncTwoPhaseSession({}, [])

    assert "at least one bind" in str(exc_info.value)


@pytest.mark.asyncio
async def test_two_phase_session_requires_at_least_one_transaction() -> None:
    dummy_connection: AsyncConnection = create_autospec(AsyncConnection, instance=True)

    with pytest.raises(InvalidRequestError) as exc_info:
        AsyncTwoPhaseSession({type(None): dummy_connection}, [])

    assert "at least one transaction" in str(exc_info.value)


def begin_twophase(connection: Connection, xid: object) -> TwoPhaseTransaction:
    return connection.begin_twophase(xid)


@pytest.mark.asyncio
async def test_two_phase_session_fails_on_second_commit(any_orms: dict[Database, ORM]) -> None:
    xid_base = XidBase(database_count=len(any_orms))

    async with AsyncExitStack() as stack:
        connection_binds: dict[type[Any], AsyncConnection] = {
            any_orms[database].wallet_class: await stack.enter_async_context(
                any_orms[database].async_engine.connect(),
            )
            for database in Database
        }

        ordered_transactions: list[TwoPhaseTransaction] = []
        for i, connection in enumerate(connection_binds.values()):
            transaction = await connection.run_sync(
                begin_twophase,
                Xid(xid_base=xid_base, database_index=i).raw_value,
            )
            ordered_transactions.append(transaction)

        async with AsyncTwoPhaseSession(connection_binds, ordered_transactions) as session:
            await async_create_wallet(
                session,
                wallet_class=any_orms[Database.A].wallet_class,
                balance=1,
            )
            await async_create_wallet(
                session,
                wallet_class=any_orms[Database.B].wallet_class,
                balance=1,
            )
            await session.commit()

            await async_create_wallet(
                session,
                wallet_class=any_orms[Database.C].wallet_class,
                balance=1,
            )

            with pytest.raises(InvalidRequestError) as exc_info:
                await session.commit()

            assert "already completed" in str(exc_info.value)
