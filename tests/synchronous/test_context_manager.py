from contextlib import suppress

from sqlalchemy.orm import Session
from support.helpers import Database, create_wallet, fail, get_wallet_balance, registered_event
from support.orm import ORM

from sqlalchemy_xa_recovery import XAOutcomeUnknownError, two_phase_session


def test_two_phase_session_commits_changes_to_all_binds(
    any_orms: dict[Database, ORM],
) -> None:
    balances: dict[Database, int] = {Database.A: 1, Database.B: 2, Database.C: 4}

    binds = {orm.wallet_class: orm.sync_engine for orm in any_orms.values()}

    with two_phase_session(binds) as session:
        for database, orm in any_orms.items():
            create_wallet(session, wallet_class=orm.wallet_class, balance=balances[database])

        session.commit()

    for database, orm in any_orms.items():
        with Session(orm.sync_engine) as session:
            balance = get_wallet_balance(session, wallet_class=orm.wallet_class)
            assert balance == balances[database]


def test_two_phase_session_leaves_data_in_corrupted_state_on_fail(
    any_orms: dict[Database, ORM],
) -> None:
    failed_engine = any_orms[Database.B].sync_engine

    default_balance = 10
    expected_balances = {
        Database.A: default_balance,
        Database.B: None,
        Database.C: None,
    }

    binds = {
        any_orms[database].wallet_class: any_orms[database].sync_engine for database in Database
    }

    with (
        registered_event(failed_engine, event_type="commit_twophase", event_handler=fail),
        suppress(XAOutcomeUnknownError),
        two_phase_session(binds) as session,
    ):
        for orm in any_orms.values():
            create_wallet(session, wallet_class=orm.wallet_class, balance=default_balance)

        session.commit()

    for database in Database:
        with Session(any_orms[database].sync_engine) as session:
            balance = get_wallet_balance(session, wallet_class=any_orms[database].wallet_class)
            assert balance == expected_balances[database]
