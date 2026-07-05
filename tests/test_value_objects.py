import pytest

from sqlalchemy_xa_recovery._value_objects import (
    InvalidXidError,
    Xid,
    XidBase,
    XidPrefix,
)


def test_raw_value_serialization_works_for_default_prefix() -> None:
    db_index, db_count = 1, 2
    xid_base = XidBase(database_count=db_count)
    xid = Xid(xid_base=xid_base, database_index=db_index)

    assert xid.raw_value == f"sxr:{xid_base.random_part}:{db_count}:{db_index}"
    assert Xid.from_raw_value(xid.raw_value) == xid


def test_raw_value_serialization_works_for_custom_prefix() -> None:
    db_index, db_count = 1, 2
    prefix = XidPrefix("myapp")

    xid_base = XidBase(database_count=db_count, prefix=prefix)
    xid = Xid(xid_base=xid_base, database_index=db_index)

    assert xid.raw_value == f"{prefix.value}:{xid_base.random_part}:{db_count}:{db_index}"
    assert Xid.from_raw_value(xid.raw_value, prefix) == xid


def test_raw_value_serialization_fails_for_mismatched_prefix() -> None:
    db_index, db_count = 1, 2
    prefix = XidPrefix("myapp")

    xid_base = XidBase(database_count=db_count, prefix=prefix)
    xid = Xid(xid_base=xid_base, database_index=db_index)

    with pytest.raises(InvalidXidError):
        Xid.from_raw_value(xid.raw_value)


@pytest.mark.parametrize(
    "raw_value",
    [
        "other:00000000000000000000000000000000:2:1",
        "sxr:not-hex:2:1",
        "sxr:00000000000000000000000000000000:0:0",
        "sxr:00000000000000000000000000000000:2:2",
        "sxr:00000000000000000000000000000000:two:1",
        "not-even-close",
        b"\xff",
    ],
)
def test_invalid_xid_is_rejected(raw_value: str | bytes) -> None:
    prefix = XidPrefix("custom")

    with pytest.raises(InvalidXidError):
        Xid.from_raw_value(raw_value, prefix)


@pytest.mark.parametrize("xid_prefix", ["UPPER", "d1gits", "loooooooog", ""])
def test_invalid_xid_prefix_is_rejected(xid_prefix: str) -> None:
    with pytest.raises(ValueError, match="does not match pattern"):
        XidBase(database_count=2, prefix=XidPrefix(xid_prefix))
