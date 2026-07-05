from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from support.containers import (
    MariaDBContainer,
    MySqlContainer,
    PostgresContainer,
)
from support.helpers import Database
from support.orm import ORM, setup_orm


@pytest.fixture(scope="session")
def pymysql_container_a() -> Generator[MySqlContainer]:
    with MySqlContainer() as container:
        yield container


@pytest.fixture(scope="session")
def pymysql_container_b() -> Generator[MySqlContainer]:
    with MySqlContainer() as container:
        yield container


@pytest.fixture(scope="session")
def pymysql_container_c() -> Generator[MySqlContainer]:
    with MySqlContainer() as container:
        yield container


@pytest.fixture(scope="session")
def mariadb_container_a() -> Generator[MariaDBContainer]:
    with MariaDBContainer() as container:
        yield container


@pytest.fixture(scope="session")
def mariadb_container_b() -> Generator[MariaDBContainer]:
    with MariaDBContainer() as container:
        yield container


@pytest.fixture(scope="session")
def mariadb_container_c() -> Generator[MariaDBContainer]:
    with MariaDBContainer() as container:
        yield container


@pytest.fixture(scope="session")
def psycopg_container_a() -> Generator[PostgresContainer]:
    with PostgresContainer() as container:
        yield container


@pytest.fixture(scope="session")
def psycopg_container_b() -> Generator[PostgresContainer]:
    with PostgresContainer() as container:
        yield container


@pytest.fixture(scope="session")
def psycopg_container_c() -> Generator[PostgresContainer]:
    with PostgresContainer() as container:
        yield container


@pytest_asyncio.fixture
async def pymysql_orms(
    pymysql_container_a: MySqlContainer,
    pymysql_container_b: MySqlContainer,
    pymysql_container_c: MySqlContainer,
) -> AsyncGenerator[dict[Database, ORM]]:
    async with (
        setup_orm(pymysql_container_a) as orm_a,
        setup_orm(pymysql_container_b) as orm_b,
        setup_orm(pymysql_container_c) as orm_c,
    ):
        yield {
            Database.A: orm_a,
            Database.B: orm_b,
            Database.C: orm_c,
        }


@pytest_asyncio.fixture
async def mariadb_orms(
    mariadb_container_a: MariaDBContainer,
    mariadb_container_b: MariaDBContainer,
    mariadb_container_c: MariaDBContainer,
) -> AsyncGenerator[dict[Database, ORM]]:
    async with (
        setup_orm(mariadb_container_a) as orm_a,
        setup_orm(mariadb_container_b) as orm_b,
        setup_orm(mariadb_container_c) as orm_c,
    ):
        yield {
            Database.A: orm_a,
            Database.B: orm_b,
            Database.C: orm_c,
        }


@pytest_asyncio.fixture
async def psycopg_orms(
    psycopg_container_a: PostgresContainer,
    psycopg_container_b: PostgresContainer,
    psycopg_container_c: PostgresContainer,
) -> AsyncGenerator[dict[Database, ORM]]:
    async with (
        setup_orm(psycopg_container_a) as orm_a,
        setup_orm(psycopg_container_b) as orm_b,
        setup_orm(psycopg_container_c) as orm_c,
    ):
        yield {
            Database.A: orm_a,
            Database.B: orm_b,
            Database.C: orm_c,
        }


@pytest_asyncio.fixture(
    params=[
        ("pymysql_container_a", "pymysql_container_b", "pymysql_container_c"),
        ("mariadb_container_a", "mariadb_container_b", "mariadb_container_c"),
        ("psycopg_container_a", "psycopg_container_b", "psycopg_container_c"),
    ],
    ids=["mysql", "mariadb", "postgresql"],
)
async def any_orms(request: FixtureRequest) -> AsyncGenerator[dict[Database, ORM]]:
    container_a = request.getfixturevalue(request.param[0])
    container_b = request.getfixturevalue(request.param[1])
    container_c = request.getfixturevalue(request.param[2])

    async with (
        setup_orm(container_a) as orm_a,
        setup_orm(container_b) as orm_b,
        setup_orm(container_c) as orm_c,
    ):
        yield {
            Database.A: orm_a,
            Database.B: orm_b,
            Database.C: orm_c,
        }
