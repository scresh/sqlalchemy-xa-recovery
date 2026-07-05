from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import URL, Engine, Identity, Integer, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sqlalchemy_xa_recovery import XidPrefix
from sqlalchemy_xa_recovery._dialects.factory import get_dialect


class Container(ABC):
    @abstractmethod
    def get_sync_url(self) -> URL:
        raise NotImplementedError

    @abstractmethod
    def get_async_url(self) -> URL:
        raise NotImplementedError


class Wallet:
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    if TYPE_CHECKING:

        def __init__(self, balance: int = 0) -> None: ...


@dataclass
class ORM:
    async_engine: AsyncEngine
    sync_engine: Engine
    wallet_class: type[Wallet]


def rollback_prepared_transactions(engine: Engine) -> None:
    engine.dispose()

    dialect = get_dialect(engine)
    xid_prefix = XidPrefix()

    for xid in dialect.get_prepared_transactions(engine, xid_prefix):
        try:
            dialect.rollback_prepared_transaction(engine, xid)
        except Exception as e:
            if "ORA-24756" not in str(e):
                raise


@asynccontextmanager
async def setup_orm(container: Container) -> AsyncGenerator[ORM]:
    sync_engine = create_engine(container.get_sync_url(), pool_pre_ping=True)
    async_engine = create_async_engine(container.get_async_url(), pool_pre_ping=True)

    class Base(DeclarativeBase):
        pass

    class _Wallet(Wallet, Base):
        __tablename__ = "wallet"

    try:
        rollback_prepared_transactions(sync_engine)
        Base.metadata.drop_all(sync_engine)
        Base.metadata.create_all(sync_engine)

        with sync_engine.begin() as connection:
            connection.execute(text("SELECT 1"))

        yield ORM(async_engine=async_engine, sync_engine=sync_engine, wallet_class=_Wallet)

        rollback_prepared_transactions(sync_engine)
        Base.metadata.drop_all(sync_engine)
    finally:
        await async_engine.dispose()
        sync_engine.dispose()
