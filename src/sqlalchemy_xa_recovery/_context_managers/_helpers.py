from __future__ import annotations

import typing
from collections import OrderedDict
from typing import TypeVar

from sqlalchemy import Connection, TwoPhaseTransaction

EngineT = TypeVar("EngineT")


def reverse_binds(
    binds: dict[type[typing.Any], EngineT],
) -> OrderedDict[EngineT, list[type[typing.Any]]]:
    reversed_binds: OrderedDict[EngineT, list[type[typing.Any]]] = OrderedDict()

    for table, engine in binds.items():
        reversed_binds.setdefault(engine, []).append(table)

    return reversed_binds


def begin_twophase(connection: Connection, xid: object) -> TwoPhaseTransaction:
    return connection.begin_twophase(xid)
