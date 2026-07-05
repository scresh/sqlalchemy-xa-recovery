# sqlalchemy-xa-recovery

Recoverable two-phase transaction helpers for SQLAlchemy.

`sqlalchemy-xa-recovery` helps coordinate one logical transaction across multiple
SQLAlchemy engines and provides a recovery routine for prepared XA transactions
left behind after process crashes, connection failures, or uncertain commit
outcomes.

## Why this library exists

SQLAlchemy already exposes two-phase transaction primitives, but using them
directly leaves important operational work to the application:

- generating transaction identifiers that can be understood later,
- starting matching transaction branches across multiple engines,
- handling failures during prepare or commit,
- discovering prepared transactions after a crash,
- deciding whether an incomplete distributed transaction should be committed or
  rolled back.

This library adds those missing pieces around SQLAlchemy's two-phase support. It
does not replace your database XA implementation; it gives your application a
small, recoverable coordination layer on top of it.

## Installation

```bash
pip install sqlalchemy-xa-recovery
```

The package requires Python 3.11 or newer and SQLAlchemy 2.x.

## Supported databases

The current implementation supports:

- PostgreSQL
- MySQL
- MariaDB

Database-specific recovery is handled internally. PostgreSQL uses
`pg_prepared_xacts`, MySQL and MariaDB use `XA RECOVER`.

## Basic usage

Pass a mapping of ORM mapped classes to SQLAlchemy engines. The context manager
opens one connection per participating engine, starts one two-phase transaction
branch per engine, and returns a SQLAlchemy session bound to those connections.
If several mapped classes are bound to the same engine, they share that engine's
connection and transaction branch.

```python
from sqlalchemy import create_engine

from sqlalchemy_xa_recovery import two_phase_session
from myapp.models import Account, LedgerEntry

accounts_engine = create_engine("postgresql+psycopg://user:pass@db-a/app")
ledger_engine = create_engine("postgresql+psycopg://user:pass@db-b/app")

binds = {
    Account: accounts_engine,
    LedgerEntry: ledger_engine,
}

with two_phase_session(binds) as session:
    session.add(Account(id=1, balance=90))
    session.add(LedgerEntry(account_id=1, amount=-10))

    session.commit()
```

If the commit completes successfully, all transaction branches are committed. If
regular application code raises before commit, the active branches are rolled
back.

By default, generated XA identifiers use the `sxr` prefix so recovery can
distinguish this library's transactions from other prepared transactions in the
same database. Use `XidPrefix` to customize that marker for a deployment; custom
prefixes must contain only lowercase letters and be between one and eight
characters long:

```python
from sqlalchemy_xa_recovery import XidPrefix

with two_phase_session(binds, xid_prefix=XidPrefix("billing")) as session:
    # write to multiple databases
    session.commit()
```

## Async usage

The async API follows the same shape, using `AsyncEngine` objects and
`async_two_phase_session`.

```python
from sqlalchemy.ext.asyncio import create_async_engine

from sqlalchemy_xa_recovery import async_two_phase_session
from myapp.models import Account, LedgerEntry

accounts_engine = create_async_engine("postgresql+psycopg_async://user:pass@db-a/app")
ledger_engine = create_async_engine("postgresql+psycopg_async://user:pass@db-b/app")

binds = {
    Account: accounts_engine,
    LedgerEntry: ledger_engine,
}

async with async_two_phase_session(binds) as session:
    session.add(Account(id=1, balance=90))
    session.add(LedgerEntry(account_id=1, amount=-10))

    await session.commit()
```

## Recovery

When a failure happens during two-phase commit, the outcome may be unknown: some
databases may already have committed while others may still hold prepared
transactions. In that case the session raises `XAOutcomeUnknownError`.

Recovery is designed to run as a separate recurring operational task. That task
should call `recover_xa_transactions()` often enough for your tolerance for
stuck prepared transactions.

```python
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy_xa_recovery import XidPrefix, recover_xa_transactions

engines = [
    create_engine("postgresql+psycopg://user:pass@db-a/app"),
    create_engine("postgresql+psycopg://user:pass@db-b/app"),
]

recover_xa_transactions(
    all_engines=engines,
    grace_period=timedelta(seconds=15),
    xid_prefix=XidPrefix("billing"),
)
```

Run this script with cron, a scheduler, a maintenance worker, or your
orchestration platform.

Always pass every engine that can be part of the distributed transaction group.
Recovery decisions are made by comparing prepared transaction identifiers across
the full set of participating databases. If you customize `xid_prefix` for
writers, use the same prefix in the recurring recovery process.

`recover_xa_transactions()` is synchronous. For transactions written with
`async_two_phase_session()`, pass the synchronous engines behind the async
engines, for example `my_async_engine.sync_engine`.

## How it works

For each distributed transaction, the library generates a shared base identifier
and one database-specific transaction identifier. The serialized identifier
contains the prefix, a shared random transaction part, the number of
participating databases, and the branch index.

For a transaction spanning three databases, the branch XIDs may look like this:

```text
sxr:4f9c2a1b0e3d7788:3:0
sxr:4f9c2a1b0e3d7788:3:1
sxr:4f9c2a1b0e3d7788:3:2
```

Here `sxr` is the prefix, `4f9c2a1b0e3d7788` is the shared random part, `3` is
the database count, and the final value is the branch index.

During `commit()`, the session:

1. flushes pending ORM changes,
2. prepares every enlisted two-phase transaction in branch order, for example
   `0 -> 1 -> 2`,
3. commits the prepared transactions in the same order, for example
   `0 -> 1 -> 2`.

If prepare or commit fails, the library raises `XAOutcomeUnknownError` because
the application can no longer safely infer the final outcome from the local
process alone.

Recovery works by scanning each database for prepared transactions, waiting for
the configured grace period, and scanning again. Only transaction identifiers
that are still present after the grace period are considered stuck.

Stuck prepared branches are grouped by their shared transaction identifier. With
full branch order `[0, 1, 2]`, sequential `PREPARE` adds prepared branches from
the start: `[0]`, then `[0, 1]`, then `[0, 1, 2]`. Sequential `COMMIT` removes
prepared branches from the start: `[0, 1, 2]`, then `[1, 2]`, then `[2]`, then
none.

Recovery decisions follow from that shape:

- `[0]` and `[0, 1]` are prefixes, so recovery treats the prepare phase as
  incomplete and rolls them back in descending branch order;
- `[0, 1, 2]`, `[1, 2]`, and `[2]` are treated as suffixes, so recovery treats
  the transaction as fully prepared or already committing and commits them in
  ascending branch order;
- `[1]` and `[0, 2]` are neither prefixes nor suffixes, so recovery raises
  `InvalidRecoveryStateError`. The same error is raised if the XID references
  more databases than the configured engine list contains.

This gives the application a deterministic way to finish incomplete distributed
transactions after an uncertain failure.

## Operational notes

PostgreSQL must allow prepared transactions (`max_prepared_transactions > 0`).

Prepared transactions hold database resources until they are committed or rolled
back. Monitor them in production and run recovery regularly. The grace period
keeps recovery from touching transactions that are still being actively completed
by another process.

## Development

This repository uses `uv` for local development.

```bash
uv sync
uv run pytest
```

The test suite uses Testcontainers and requires Docker. It starts PostgreSQL,
MySQL, and MariaDB containers to verify both synchronous and asynchronous
transaction flows.
