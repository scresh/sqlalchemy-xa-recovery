"""Utilities for recovering prepared XA transactions."""

from datetime import timedelta
from time import sleep

from sqlalchemy import Engine

from sqlalchemy_xa_recovery._dialects.factory import get_dialect
from sqlalchemy_xa_recovery._value_objects import Xid, XidBase, XidPrefix


class InvalidRecoveryStateError(Exception):
    """Raised when recovered XA branches cannot be completed safely."""


def _get_stuck_xids(
    engine: Engine,
    grace_period: timedelta,
    xid_prefix: XidPrefix,
) -> set[Xid]:
    """Return parsed XA identifiers still present after the grace period."""
    dialect = get_dialect(engine)

    xids_before: set[Xid] = dialect.get_prepared_transactions(engine, xid_prefix)
    sleep(grace_period.total_seconds())
    xids_after: set[Xid] = dialect.get_prepared_transactions(engine, xid_prefix)

    return xids_before & xids_after


def _sort_xids_and_engines(
    xids_and_engines: list[tuple[Xid, Engine]],
    *,
    reverse: bool,
) -> list[tuple[Xid, Engine]]:
    return sorted(
        xids_and_engines,
        key=lambda xid_and_engine: xid_and_engine[0].database_index,
        reverse=reverse,
    )


def _should_commit_group(
    xid_base: XidBase,
    xids_and_engines: list[tuple[Xid, Engine]],
    engine_count: int,
) -> bool:
    if xid_base.database_count > engine_count:
        raise InvalidRecoveryStateError(
            "Recovered XA transaction references more databases than configured",
        )

    indexes: list[int] = sorted(xid.database_index for xid, _ in xids_and_engines)
    all_indexes: list[int] = list(range(xid_base.database_count))

    if indexes == all_indexes[-len(indexes) :]:
        return True
    if indexes == all_indexes[: len(indexes)]:
        return False

    raise InvalidRecoveryStateError("Recovered XA transaction branches are not prefix or suffix")


def _commit(xids_and_engines: list[tuple[Xid, Engine]]) -> None:
    for xid, engine in _sort_xids_and_engines(xids_and_engines, reverse=False):
        dialect = get_dialect(engine)
        dialect.commit_prepared_transaction(engine, xid)


def _rollback(xids_and_engines: list[tuple[Xid, Engine]]) -> None:
    for xid, engine in _sort_xids_and_engines(xids_and_engines, reverse=True):
        dialect = get_dialect(engine)
        dialect.rollback_prepared_transaction(engine, xid)


def recover_xa_transactions(
    all_engines: list[Engine],
    grace_period: timedelta = timedelta(seconds=15),
    xid_prefix: XidPrefix | None = None,
) -> None:
    """Recover stuck XA transactions across all configured engines."""
    xid_prefix: XidPrefix = xid_prefix or XidPrefix()

    all_stuck_xids: list[set[Xid]] = [
        _get_stuck_xids(engine, grace_period, xid_prefix) for engine in all_engines
    ]

    grouped_xids_and_engines: dict[XidBase, list[tuple[Xid, Engine]]] = {}

    for engine, engine_stuck_xids in zip(all_engines, all_stuck_xids, strict=True):
        for xid in engine_stuck_xids:
            grouped_xids_and_engines.setdefault(xid.xid_base, []).append((xid, engine))

    for xid_base, xids_and_engines in grouped_xids_and_engines.items():
        should_commit = _should_commit_group(
            xid_base,
            xids_and_engines,
            engine_count=len(all_engines),
        )

        if should_commit:
            _commit(xids_and_engines)
        else:
            _rollback(xids_and_engines)
