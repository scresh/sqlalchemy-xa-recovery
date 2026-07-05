from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from enum import StrEnum
from typing import Any

from sqlalchemy import Engine, event, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from support.orm import Wallet


@contextmanager
def registered_event(
    engine: Engine,
    event_type: str,
    event_handler: Callable[..., Any],
) -> Iterator[Engine]:
    try:
        event.listen(engine, event_type, event_handler)
        yield engine
    finally:
        with suppress(Exception):
            event.remove(engine, event_type, event_handler)


def fail(*_: Any) -> None:  # noqa: ANN401
    raise BaseException  # noqa: TRY002


def create_wallet(session: Session, wallet_class: type[Wallet], balance: int) -> None:
    wallet = wallet_class(balance=balance)
    session.add(wallet)
    session.flush()


async def async_create_wallet(
    session: AsyncSession,
    wallet_class: type[Wallet],
    balance: int,
) -> None:
    wallet = wallet_class(balance=balance)
    session.add(wallet)
    await session.flush()


def get_wallet_balance(
    session: Session,
    wallet_class: type[Wallet],
) -> int | None:
    result = session.execute(select(wallet_class)).scalar_one_or_none()

    if result is None:
        return None

    return result.balance


async def async_get_wallet_balance(
    session: AsyncSession,
    wallet_class: type[Wallet],
) -> int | None:
    result = (await session.execute(select(wallet_class))).scalar_one_or_none()

    if result is None:
        return None

    return result.balance


class Database(StrEnum):
    A = "A"
    B = "B"
    C = "C"
