from secrets import token_hex

from sqlalchemy import URL, make_url
from testcontainers.mysql import MySqlContainer as _MySql
from testcontainers.postgres import PostgresContainer as _Postgres

from support.orm import Container


class MySqlContainer(_MySql, Container):
    def __init__(self) -> None:
        super().__init__(
            image="mysql:9.7.0",
            username="root",
            password=token_hex(),
            dbname="test_db",
        )

    def get_sync_url(self) -> URL:
        return make_url(self.get_connection_url()).set(drivername="mysql+pymysql")

    def get_async_url(self) -> URL:
        return make_url(self.get_connection_url()).set(drivername="mysql+aiomysql")


class MariaDBContainer(_MySql, Container):
    def __init__(self) -> None:
        super().__init__(
            image="mariadb:11",
            username="root",
            password=token_hex(),
            dbname="test_db",
        )

    def get_sync_url(self) -> URL:
        return make_url(self.get_connection_url()).set(drivername="mariadb+pymysql")

    def get_async_url(self) -> URL:
        return make_url(self.get_connection_url()).set(drivername="mariadb+aiomysql")


class PostgresContainer(_Postgres, Container):
    def __init__(self) -> None:
        super().__init__(
            image="postgres:18.3",
            username="root",
            password=token_hex(),
            dbname="test_db",
        )
        self._command = "postgres -c max_prepared_transactions=10"

    def get_sync_url(self) -> URL:
        return make_url(self.get_connection_url()).set(drivername="postgresql+psycopg")

    def get_async_url(self) -> URL:
        return make_url(self.get_connection_url()).set(drivername="postgresql+psycopg_async")
