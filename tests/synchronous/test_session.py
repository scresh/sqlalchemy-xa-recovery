from contextlib import ExitStack
from typing import Any
from unittest.mock import create_autospec

import pytest
from sqlalchemy import Connection, TwoPhaseTransaction
from sqlalchemy.exc import InvalidRequestError
from support.helpers import Database, create_wallet
from support.orm import ORM

from sqlalchemy_xa_recovery import TwoPhaseSession
from sqlalchemy_xa_recovery._value_objects import Xid, XidBase


def test_two_phase_session_requires_at_least_one_bind() -> None:
    with pytest.raises(InvalidRequestError) as exc_info:
        TwoPhaseSession({}, [])

    assert "at least one bind" in str(exc_info.value)


def test_two_phase_session_requires_at_least_one_transaction() -> None:
    dummy_connection: Connection = create_autospec(Connection, instance=True)

    with pytest.raises(InvalidRequestError) as exc_info:
        TwoPhaseSession({type(None): dummy_connection}, [])

    assert "at least one transaction" in str(exc_info.value)


def test_two_phase_session_fails_on_second_commit(
    any_orms: dict[Database, ORM],
) -> None:
    xid_base = XidBase(database_count=len(any_orms))

    with ExitStack() as stack:
        connection_binds: dict[type[Any], Connection] = {
            any_orms[database].wallet_class: stack.enter_context(
                any_orms[database].sync_engine.connect(),
            )
            for database in Database
        }

        ordered_transactions: list[TwoPhaseTransaction] = [
            c.begin_twophase(Xid(xid_base=xid_base, database_index=i).raw_value)
            for i, c in enumerate(connection_binds.values())
        ]

        with TwoPhaseSession(connection_binds, ordered_transactions) as session:
            create_wallet(session, wallet_class=any_orms[Database.A].wallet_class, balance=1)
            create_wallet(session, wallet_class=any_orms[Database.B].wallet_class, balance=1)
            session.commit()

            create_wallet(session, wallet_class=any_orms[Database.C].wallet_class, balance=1)

            with pytest.raises(InvalidRequestError) as exc_info:
                session.commit()

            assert "already completed" in str(exc_info.value)
