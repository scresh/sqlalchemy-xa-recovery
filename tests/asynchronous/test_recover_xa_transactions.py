from contextlib import suppress
from datetime import timedelta

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

from sqlalchemy_xa_recovery import (
    XAOutcomeUnknownError,
    XidPrefix,
    async_two_phase_session,
    recover_xa_transactions,
)
from sqlalchemy_xa_recovery._dialects.factory import get_dialect


@pytest.mark.asyncio
async def test_recover_xa_transactions_with_started_commit_commits_remaining_transactions(
    any_orms: dict[Database, ORM],
) -> None:
    failed_engine = any_orms[Database.B].async_engine.sync_engine

    default_balance = 10
    expected_balances_before = {
        Database.A: default_balance,
        Database.B: None,
        Database.C: None,
    }
    expected_balances_after = {
        Database.A: default_balance,
        Database.B: default_balance,
        Database.C: default_balance,
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
            assert balance == expected_balances_before[database]

    recover_xa_transactions(
        all_engines=[x.sync_engine for x in any_orms.values()],
        grace_period=timedelta(seconds=0),
    )

    for database in Database:
        async with AsyncSession(any_orms[database].async_engine) as session:
            balance = await async_get_wallet_balance(
                session,
                wallet_class=any_orms[database].wallet_class,
            )
            assert balance == expected_balances_after[database]


@pytest.mark.asyncio
async def test_recover_xa_transactions_with_unstarted_commit_rolls_back_remaining_transactions(
    any_orms: dict[Database, ORM],
) -> None:
    xid_prefix = XidPrefix()
    failed_engine = any_orms[Database.B].async_engine.sync_engine

    default_balance = 10
    expected_balances = {
        Database.A: None,
        Database.B: None,
        Database.C: None,
    }
    expected_xid_counts_before = {
        Database.A: 1,
        Database.B: 0,
        Database.C: 0,
    }

    binds = {
        any_orms[database].wallet_class: any_orms[database].async_engine for database in Database
    }

    with (
        registered_event(failed_engine, event_type="prepare_twophase", event_handler=fail),
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
        engine = any_orms[database].sync_engine
        dialect = get_dialect(engine)

        async with AsyncSession(any_orms[database].async_engine) as session:
            balance = await async_get_wallet_balance(
                session,
                wallet_class=any_orms[database].wallet_class,
            )

        assert balance == expected_balances[database]
        assert (
            len(dialect.get_prepared_transactions(engine, xid_prefix))
            == expected_xid_counts_before[database]
        )

    recover_xa_transactions(
        all_engines=[x.sync_engine for x in any_orms.values()],
        grace_period=timedelta(seconds=0),
    )

    for database in Database:
        engine = any_orms[database].sync_engine
        dialect = get_dialect(engine)

        async with AsyncSession(any_orms[database].async_engine) as session:
            balance = await async_get_wallet_balance(
                session,
                wallet_class=any_orms[database].wallet_class,
            )

        assert balance == expected_balances[database]
        assert len(dialect.get_prepared_transactions(engine, xid_prefix)) == 0
