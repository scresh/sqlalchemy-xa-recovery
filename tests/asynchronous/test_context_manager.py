from contextlib import suppress

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from support.helpers import (
    Database,
    async_create_wallet,
    async_get_wallet_balance,
    fail,
    registered_event,
)
from support.orm import ORM

from sqlalchemy_xa_recovery import XAOutcomeUnknownError, async_two_phase_session


@pytest.mark.asyncio
async def test_two_phase_session_commits_changes_to_all_binds(
    any_orms: dict[Database, ORM],
) -> None:
    balances: dict[Database, int] = {Database.A: 1, Database.B: 2, Database.C: 4}

    binds = {orm.wallet_class: orm.async_engine for orm in any_orms.values()}

    async with async_two_phase_session(binds) as session:
        for database, orm in any_orms.items():
            await async_create_wallet(
                session,
                wallet_class=orm.wallet_class,
                balance=balances[database],
            )

        await session.commit()

    for database, orm in any_orms.items():
        async with AsyncSession(orm.async_engine) as session:
            balance = await async_get_wallet_balance(session, wallet_class=orm.wallet_class)
            assert balance == balances[database]


@pytest.mark.asyncio
async def test_two_phase_session_leaves_data_in_corrupted_state_on_fail(
    any_orms: dict[Database, ORM],
) -> None:
    failed_engine = any_orms[Database.B].async_engine.sync_engine

    default_balance = 10
    expected_balances = {
        Database.A: default_balance,
        Database.B: None,
        Database.C: None,
    }

    binds = {
        any_orms[database].wallet_class: any_orms[database].async_engine for database in Database
    }

    with (
        registered_event(failed_engine, event_type="commit_twophase", event_handler=fail),
        suppress(XAOutcomeUnknownError),
    ):
        async with async_two_phase_session(binds) as session:
            for orm in any_orms.values():
                await async_create_wallet(
                    session,
                    wallet_class=orm.wallet_class,
                    balance=default_balance,
                )

            await session.commit()

    for database in Database:
        async with AsyncSession(any_orms[database].async_engine) as session:
            balance = await async_get_wallet_balance(
                session,
                wallet_class=any_orms[database].wallet_class,
            )
            assert balance == expected_balances[database]
