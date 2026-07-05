"""Value objects for SQLAlchemy two-phase transaction identifiers."""

import re
from dataclasses import dataclass, field
from functools import partial
from secrets import token_hex
from typing import ClassVar, Self


class InvalidXidError(ValueError):
    """Raised when a raw XA transaction identifier is not owned by this library."""


@dataclass(frozen=True, slots=True, order=True)
class XidPrefix:
    value: str = "sxr"

    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z]{1,8}$")

    def __post_init__(self) -> None:
        if self.PATTERN.fullmatch(self.value) is None:
            raise ValueError("XID prefix does not match pattern")


@dataclass(frozen=True, slots=True, order=True)
class XidBase:
    """Shared transaction identifier data for all databases in one XA operation."""

    database_count: int
    prefix: XidPrefix = field(default_factory=XidPrefix)
    random_part: str = field(default_factory=partial(token_hex, 8))

    SEPARATOR: ClassVar[str] = ":"

    def __post_init__(self) -> None:
        if self.database_count < 1:
            raise ValueError("Database count must be greater than zero")

    @property
    def ordered_indexes(self) -> list[int]:
        """Return database indexes in their recovery order."""
        return list(range(self.database_count))


@dataclass(frozen=True, slots=True, order=True)
class Xid:
    """Database-specific XA transaction identifier."""

    xid_base: XidBase
    database_index: int

    def __post_init__(self) -> None:
        if not (0 <= self.database_index < self.xid_base.database_count):
            raise ValueError("Invalid database index")

    @classmethod
    def from_raw_value(
        cls,
        raw_value: str | bytes,
        xid_prefix: XidPrefix | None = None,
    ) -> Self:
        """Parse a raw XA transaction identifier."""

        xid_prefix: XidPrefix = xid_prefix or XidPrefix()

        if isinstance(raw_value, bytes):
            try:
                raw_value = raw_value.decode()
            except UnicodeDecodeError as error:
                raise InvalidXidError from error

        random_part, database_count, database_index = cls._get_xid_parts(xid_prefix, raw_value)

        xid_base = XidBase(
            prefix=xid_prefix,
            random_part=random_part,
            database_count=database_count,
        )

        return cls(
            xid_base=xid_base,
            database_index=database_index,
        )

    @property
    def raw_value(self) -> str:
        """Return the serialized XA transaction identifier."""
        parts: list[str] = [
            self.xid_base.prefix.value,
            self.xid_base.random_part,
            str(self.xid_base.database_count),
            str(self.database_index),
        ]
        return XidBase.SEPARATOR.join(parts)

    @staticmethod
    def _get_xid_parts(xid_prefix: XidPrefix, raw_value: str) -> tuple[str, int, int]:
        escaped_prefix = re.escape(xid_prefix.value)

        xid_pattern = re.compile(
            rf"^(?P<prefix>{escaped_prefix}):"
            r"(?P<random_part>[0-9a-f]{16}):"
            r"(?P<database_count>[1-9][0-9]*):"
            r"(?P<database_index>0|[1-9][0-9]*)$",
        )

        match = xid_pattern.fullmatch(raw_value)

        if match is None:
            raise InvalidXidError("Invalid XA transaction identifier format")

        random_part = match["random_part"]
        database_count = int(match["database_count"])
        database_index = int(match["database_index"])

        return random_part, database_count, database_index
