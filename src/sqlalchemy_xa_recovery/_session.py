"""Two-phase SQLAlchemy session primitives."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Connection, TwoPhaseTransaction
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import Session


class XAOutcomeUnknownError(Exception):
    """Raised when a two-phase commit outcome cannot be determined."""


class TwoPhaseSession(Session):
    """SQLAlchemy session that coordinates externally started XA transactions."""

    def __init__(
        self,
        binds: dict[type[Any], Connection],
        ordered_transactions: list[TwoPhaseTransaction],
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Create a session bound to prepared two-phase transactions."""

        if not binds:
            raise InvalidRequestError("Two-phase session requires at least one bind")

        if not ordered_transactions:
            raise InvalidRequestError("Two-phase session requires at least one transaction")

        super().__init__(
            binds=binds.copy(),  # ty: ignore[invalid-argument-type]
            **kwargs,
        )

        self._ordered_transactions: list[TwoPhaseTransaction] = ordered_transactions
        self._xa_completed: bool = False

    @property
    def xa_completed(self) -> bool:
        return self._xa_completed

    def commit(self) -> None:
        """Prepare and commit all enlisted transactions in order."""

        if self._xa_completed:
            raise InvalidRequestError("This two-phase session has already completed")

        self.flush()

        try:
            for transaction in self._ordered_transactions:
                transaction.prepare()

            for transaction in self._ordered_transactions:
                transaction.commit()
        except BaseException as e:
            raise XAOutcomeUnknownError from e

        self._ordered_transactions.clear()
        self._xa_completed = True

    def rollback(self) -> None:
        """Roll back every still-active enlisted transaction."""

        if self._xa_completed:
            raise InvalidRequestError("This two-phase session has already completed")

        for transaction in self._ordered_transactions:
            if transaction.is_active:
                transaction.rollback()

        self._ordered_transactions.clear()
        self._xa_completed = True


class AsyncTwoPhaseSession(AsyncSession):
    """Async SQLAlchemy session backed by the synchronous two-phase session."""

    sync_session_class = TwoPhaseSession

    def __init__(
        self,
        binds: dict[type[Any], AsyncConnection],
        ordered_transactions: list[TwoPhaseTransaction],
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Create an async session bound to prepared two-phase transactions."""
        super().__init__(
            binds=binds.copy(),  # ty: ignore[invalid-argument-type]
            ordered_transactions=ordered_transactions,
            **kwargs,
        )

    @property
    def xa_completed(self) -> bool:
        return cast("TwoPhaseSession", self.sync_session).xa_completed
