from sqlalchemy import Engine, text

from sqlalchemy_xa_recovery._dialects.base import TwoPhaseDialect, parse_recovered_xids
from sqlalchemy_xa_recovery._value_objects import Xid, XidPrefix


class Postgres(TwoPhaseDialect):
    @staticmethod
    def get_prepared_transactions(engine: Engine, xid_prefix: XidPrefix) -> set[Xid]:
        statement = text(
            """
            SELECT gid
            FROM pg_prepared_xacts
            WHERE database = current_database()
            """,
        )

        with engine.connect() as connection:
            raw_xids = list(connection.execute(statement).scalars())

        return parse_recovered_xids(raw_xids, xid_prefix)

    @staticmethod
    def rollback_prepared_transaction(engine: Engine, transaction_id: Xid) -> None:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(
                f"ROLLBACK PREPARED '{transaction_id.raw_value}'",
            )

    @staticmethod
    def commit_prepared_transaction(engine: Engine, transaction_id: Xid) -> None:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(
                f"COMMIT PREPARED '{transaction_id.raw_value}'",
            )
