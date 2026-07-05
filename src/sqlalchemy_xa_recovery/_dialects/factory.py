from enum import StrEnum

from sqlalchemy import Engine

from sqlalchemy_xa_recovery._dialects.base import TwoPhaseDialect
from sqlalchemy_xa_recovery._dialects.mysql import MySQL
from sqlalchemy_xa_recovery._dialects.postgres import Postgres


class DialectName(StrEnum):
    MYSQL = "mysql"
    MARIADB = "mariadb"
    POSTGRES = "postgresql"


DIALECTS: dict[DialectName, type[TwoPhaseDialect]] = {
    DialectName.MYSQL: MySQL,
    DialectName.MARIADB: MySQL,
    DialectName.POSTGRES: Postgres,
}


def get_dialect(engine: Engine) -> type[TwoPhaseDialect]:
    dialect_name: DialectName = DialectName(engine.dialect.name)
    return DIALECTS[dialect_name]
