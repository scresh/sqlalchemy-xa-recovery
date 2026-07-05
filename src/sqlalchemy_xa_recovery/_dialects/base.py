from abc import ABC, abstractmethod
from contextlib import suppress

from sqlalchemy import Engine

from sqlalchemy_xa_recovery._value_objects import InvalidXidError, Xid, XidPrefix


def parse_recovered_xids(raw_values: list[str | bytes], xid_prefix: XidPrefix) -> set[Xid]:
    """Parse a recovered XID, ignoring identifiers owned by other systems."""

    recovered_xids: set[Xid] = set()

    for raw_value in raw_values:
        with suppress(InvalidXidError):
            recovered_xids.add(Xid.from_raw_value(raw_value, xid_prefix=xid_prefix))

    return recovered_xids


class TwoPhaseDialect(ABC):
    @staticmethod
    @abstractmethod
    def get_prepared_transactions(engine: Engine, xid_prefix: XidPrefix) -> set[Xid]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def rollback_prepared_transaction(engine: Engine, transaction_id: Xid) -> None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def commit_prepared_transaction(engine: Engine, transaction_id: Xid) -> None:
        raise NotImplementedError
