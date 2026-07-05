from sqlalchemy import Engine, text

from sqlalchemy_xa_recovery._dialects.base import TwoPhaseDialect, parse_recovered_xids
from sqlalchemy_xa_recovery._value_objects import Xid, XidPrefix


class MySQL(TwoPhaseDialect):
    @staticmethod
    def get_prepared_transactions(engine: Engine, xid_prefix: XidPrefix) -> set[Xid]:
        statement = text("XA RECOVER")

        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            raw_xids = [raw_xid for (*_, raw_xid) in connection.execute(statement).fetchall()]

        return parse_recovered_xids(raw_xids, xid_prefix)

    @staticmethod
    def rollback_prepared_transaction(engine: Engine, transaction_id: Xid) -> None:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(
                statement=text("XA ROLLBACK :xid"),
                parameters={"xid": transaction_id.raw_value},
            )

    @staticmethod
    def commit_prepared_transaction(engine: Engine, transaction_id: Xid) -> None:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(
                statement=text("XA COMMIT :xid"),
                parameters={"xid": transaction_id.raw_value},
            )
