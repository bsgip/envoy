from datetime import datetime
from typing import Optional, Union

import pytest
from sqlalchemy import BOOLEAN, FLOAT, VARCHAR, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model.base import Base
from tests.data.fake.generator import (
    generate_sql_alchemy_instance,
    generate_value,
    get_first_generatable_primitive,
    is_generatable_type,
    is_list_type,
    is_optional_type,
    is_passthrough_type,
    is_sql_alchemy_type,
    remove_passthrough_type,
)


class ParentClass(Base):
    """This is to stress test our data faking tools. It will never be installed in a database"""
    __tablename__ = "_parent"

    parent_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(VARCHAR(length=11), nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    total: Mapped[float] = mapped_column(FLOAT, nullable=False)
    children: Mapped[list["ChildClass"]] = relationship(back_populates="parent")

    UniqueConstraint("name", "created", name="name_created")


class ChildClass(Base):
    """This is to stress test our data faking tools. It will never be installed in a database"""
    __tablename__ = "_child"

    child_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("_parent.parent_id"))
    name: Mapped[str] = mapped_column(VARCHAR(length=11), nullable=False)
    long_name: Mapped[Optional[str]] = mapped_column(VARCHAR(length=32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    parent: Mapped["ParentClass"] = relationship(back_populates="children")

Base.metadata

def test_generate_value():
    """This won't exhaustively test all types - it's just a quick sanity check on the generation code"""
    assert isinstance(generate_value(int, 1), int)
    assert generate_value(int, 1) != generate_value(int, 2)
    assert generate_value(int, 1, True) != generate_value(int, 2, True)
    assert generate_value(Optional[int], 1, True) is None
    assert generate_value(Optional[int], 2, True) is None

    assert isinstance(generate_value(str, 1), str)
    assert generate_value(str, 1) != generate_value(str, 2)
    assert generate_value(str, 1, True) != generate_value(str, 2, True)
    assert generate_value(Optional[str], 1, True) is None
    assert generate_value(Optional[str], 2, True) is None

    # unknown types should error out
    with pytest.raises(Exception):
        generate_value(ParentClass, 1)
    with pytest.raises(Exception):
        generate_value(list[int], 1)


def test_is_sql_alchemy_type():
    assert is_sql_alchemy_type(ParentClass)
    assert is_sql_alchemy_type(ChildClass)
    assert not is_sql_alchemy_type(str)


def test_is_optional_type():
    assert is_optional_type(Optional[datetime])
    assert is_optional_type(Optional[int])
    assert is_optional_type(Optional[str])
    assert is_optional_type(Union[type(None), str])
    assert is_optional_type(Union[str, type(None)])

    assert not is_optional_type(ParentClass)
    assert not is_optional_type(ChildClass)
    assert not is_optional_type(Union[int, str])


def test_is_list_type():
    assert is_list_type(list[ParentClass])
    assert is_list_type(list[int])

    assert not is_list_type(Mapped[int])
    assert not is_list_type(int)
    assert not is_list_type(ParentClass)


def test_is_passthrough_type():
    assert is_passthrough_type(Mapped[int])
    assert is_passthrough_type(Mapped[Optional[int]])
    assert is_passthrough_type(Mapped[Union[str, int]])

    assert not is_passthrough_type(Union[str, int])
    assert not is_passthrough_type(str)
    assert not is_passthrough_type(list[int])


def test_remove_passthrough_type():
    assert remove_passthrough_type(str) == str
    assert remove_passthrough_type(Optional[str]) == Optional[str]
    assert remove_passthrough_type(Mapped[Optional[str]]) == Optional[str]
    assert remove_passthrough_type(Mapped[str]) == str
    assert remove_passthrough_type(list[str]) == list[str]
    assert remove_passthrough_type(list[ParentClass]) == list[ParentClass]
    assert remove_passthrough_type(Mapped[list[ParentClass]]) == list[ParentClass]
    assert remove_passthrough_type(dict[str, int]) == dict[str, int]


def test_is_generatable_type():
    """Simple test cases for common is_generatable_type values"""
    assert is_generatable_type(int)
    assert is_generatable_type(str)
    assert is_generatable_type(bool)
    assert is_generatable_type(datetime)
    assert is_generatable_type(Optional[int])
    assert is_generatable_type(Union[int, str])
    assert is_generatable_type(Union[type(None), str])
    assert is_generatable_type(Mapped[Optional[int]])
    assert is_generatable_type(Mapped[Optional[datetime]])

    assert not is_generatable_type(ChildClass)
    assert not is_generatable_type(ParentClass)
    assert not is_generatable_type(Mapped[ParentClass])
    assert not is_generatable_type(Mapped[Optional[ParentClass]])

    # check collections
    assert not is_generatable_type(list[ParentClass])
    assert not is_generatable_type(list[int])
    assert not is_generatable_type(set[datetime])
    assert not is_generatable_type(dict[str, int])


def test_get_first_generatable_primitive():
    # With include_optional enabled
    assert get_first_generatable_primitive(int, include_optional=True) == int
    assert get_first_generatable_primitive(datetime, include_optional=True) == datetime
    assert get_first_generatable_primitive(str, include_optional=True) == str
    assert get_first_generatable_primitive(Optional[int], include_optional=True) == Optional[int]
    assert get_first_generatable_primitive(Union[int, str], include_optional=True) == int
    assert get_first_generatable_primitive(Union[Optional[str], int], include_optional=True) == Optional[str]
    assert get_first_generatable_primitive(Mapped[str], include_optional=True) == str
    assert get_first_generatable_primitive(Mapped[Optional[str]], include_optional=True) == Optional[str]
    assert get_first_generatable_primitive(Mapped[Optional[Union[str, int]]], include_optional=True) == Optional[str]

    assert get_first_generatable_primitive(Mapped[ParentClass], include_optional=True) is None
    assert get_first_generatable_primitive(ParentClass, include_optional=True) is None
    assert get_first_generatable_primitive(list[str], include_optional=True) is None
    assert get_first_generatable_primitive(list[int], include_optional=True) is None
    assert get_first_generatable_primitive(Mapped[list[str]], include_optional=True) is None

    # With include_optional disabled
    assert get_first_generatable_primitive(int, include_optional=False) == int
    assert get_first_generatable_primitive(datetime, include_optional=False) == datetime
    assert get_first_generatable_primitive(str, include_optional=False) == str
    assert get_first_generatable_primitive(Optional[int], include_optional=False) == int
    assert get_first_generatable_primitive(Union[int, str], include_optional=False) == int
    assert get_first_generatable_primitive(Union[Optional[str], int], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[str], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[Optional[str]], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[Optional[Union[str, int]]], include_optional=False) == str

    assert get_first_generatable_primitive(Mapped[ParentClass], include_optional=False) is None
    assert get_first_generatable_primitive(ParentClass, include_optional=False) is None
    assert get_first_generatable_primitive(list[str], include_optional=False) is None
    assert get_first_generatable_primitive(list[int], include_optional=False) is None
    assert get_first_generatable_primitive(Mapped[list[str]], include_optional=False) is None


def test_generate_sql_alchemy_instance_basic_values():
    """Simple sanity check on some models to make sure the basic assumptions of generate_sql_alchemy_instance hold"""

    c1: ChildClass = generate_sql_alchemy_instance(ChildClass)

    # Ensure we create values
    assert c1.name is not None
    assert c1.long_name is not None
    assert c1.child_id is not None
    assert c1.parent_id is not None
    assert c1.created_at is not None
    assert c1.deleted_at is not None
    assert c1.parent is None, "generate_relationships is False so this should not populate"

    assert c1.name != c1.long_name, "Checking that fields of the same type get unique values"
    assert c1.child_id != c1.parent_id, "Checking that fields of the same type get unique values"
    assert c1.created_at != c1.deleted_at, "Checking that fields of the same type get unique values"

    # create a new instance with a different seed
    c2: ChildClass = generate_sql_alchemy_instance(ChildClass, seed=123)
    assert c2.name is not None
    assert c2.long_name is not None
    assert c2.child_id is not None
    assert c2.parent_id is not None
    assert c2.created_at is not None
    assert c2.deleted_at is not None
    assert c2.parent is None, "generate_relationships is False so this should not populate"

    assert c2.name != c2.long_name, "Checking that fields of the same type get unique values"
    assert c2.child_id != c2.parent_id, "Checking that fields of the same type get unique values"
    assert c2.created_at != c2.deleted_at, "Checking that fields of the same type get unique values"

    # validate that c1 != c2
    assert c1.name != c2.name, "Checking that different seed numbers yields different results"
    assert c1.long_name != c2.long_name, "Checking that different seed numbers yields different results"
    assert c1.child_id != c2.child_id, "Checking that different seed numbers yields different results"
    assert c1.parent_id != c2.parent_id, "Checking that different seed numbers yields different results"
    assert c1.created_at != c2.created_at, "Checking that different seed numbers yields different results"
    assert c1.deleted_at != c2.deleted_at, "Checking that different seed numbers yields different results"

    # check optional_is_none
    c3: ChildClass = generate_sql_alchemy_instance(ChildClass, seed=456, optional_is_none=True)
    assert c3.name is not None
    assert c3.long_name is None, "optional_is_none is True and this is optional"
    assert c3.child_id is not None
    assert c3.parent_id is not None
    assert c3.parent is None, "generate_relationships is False so this should not populate"
    assert c3.created_at is not None
    assert c3.deleted_at is None, "optional_is_none is True and this is optional"


def test_generate_sql_alchemy_instance_single_relationships():
    """Sanity check that relationships can be generated as demanded"""

    c1: ChildClass = generate_sql_alchemy_instance(ChildClass, generate_relationships=True)

    assert c1.parent is not None, "generate_relationships is True so this should be populated"
    assert isinstance(c1.parent, ParentClass)
    assert c1.parent.name is not None
    assert c1.parent.created is not None
    assert c1.parent.deleted is not None
    assert c1.parent.disabled is not None
    assert c1.parent.children is not None and len(c1.parent.children) == 1, "Backreference should self reference"
    assert c1.parent.children[0] == c1, "Backreference should self reference"
    assert c1.parent.created != c1.parent.deleted, "Checking that fields of the same type get unique values"
    assert c1.parent.deleted != c1.parent.disabled, "Checking that fields of the same type get unique values"

    c2: ChildClass = generate_sql_alchemy_instance(ChildClass, seed=2, generate_relationships=True)
    assert c2.parent.name is not None
    assert c2.parent.created is not None
    assert c2.parent.deleted is not None
    assert c2.parent.disabled is not None
    assert c2.parent.children is not None and len(c2.parent.children) == 1, "Backreference should self reference"
    assert c2.parent.children[0] == c2, "Backreference should self reference"
    assert c2.parent.created != c2.parent.deleted, "Checking that fields of the same type get unique values"
    assert c2.parent.deleted != c2.parent.disabled, "Checking that fields of the same type get unique values"
    assert c1.parent.created != c2.parent.created, "Checking that different seed numbers yields different results"
    assert c1.parent.deleted != c2.parent.deleted, "Checking that different seed numbers yields different results"


def test_generate_sql_alchemy_instance_multi_relationships():
    """Sanity check that relationships can be generated as demanded"""

    p1: ParentClass = generate_sql_alchemy_instance(ParentClass, generate_relationships=True)

    assert p1.children is not None and len(p1.children) == 1, "generate_relationships is True so this should be populated"
    assert isinstance(p1.children[0], ChildClass)
    assert p1.children[0].child_id is not None
    assert p1.children[0].name is not None
    assert p1.children[0].long_name is not None
    assert p1.children[0].created_at is not None
    assert p1.children[0].deleted_at is not None
    assert p1.children[0].parent is not None and p1.children[0].parent == p1, "Backreference should self reference"
    assert p1.children[0].created_at != p1.children[0].deleted_at, "Checking that fields of the same type get unique values"
    assert p1.children[0].long_name != p1.children[0].name, "Checking that fields of the same type get unique values"

    p2: ParentClass = generate_sql_alchemy_instance(ParentClass, seed=2, generate_relationships=True)
    assert isinstance(p2.children[0], ChildClass)
    assert p2.children[0].child_id is not None
    assert p2.children[0].name is not None
    assert p2.children[0].long_name is not None
    assert p2.children[0].created_at is not None
    assert p2.children[0].deleted_at is not None
    assert p2.children[0].parent is not None and p2.children[0].parent == p2, "Backreference should self reference"
    assert p2.children[0].created_at != p2.children[0].deleted_at, "Checking that fields of the same type get unique values"
    assert p2.children[0].long_name != p2.children[0].name, "Checking that fields of the same type get unique values"
    assert p1.children[0].created_at != p2.children[0].created_at, "Checking that different seed numbers yields different results"
    assert p1.children[0].deleted_at != p2.children[0].deleted_at, "Checking that different seed numbers yields different results"