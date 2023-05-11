from datetime import datetime
from enum import IntFlag, auto
from typing import Optional, Union

import pytest
from pydantic_xml import BaseXmlModel, element
from sqlalchemy import BOOLEAN, FLOAT, INTEGER, VARCHAR, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from envoy.server.model.base import Base
from envoy.server.schema.sep2.base import BaseXmlModelWithNS
from tests.data.fake.generator import (
    clone_class_instance,
    generate_class_instance,
    generate_value,
    get_first_generatable_primitive,
    get_generatable_class_base,
    get_optional_type_argument,
    is_generatable_type,
    is_optional_type,
    is_passthrough_type,
    remove_passthrough_type,
)


class CustomFlags(IntFlag):
    """Various bit flags"""

    FLAG_1 = auto()
    FLAG_2 = auto()
    FLAG_3 = auto()
    FLAG_4 = auto()


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
    flags: Mapped[CustomFlags] = mapped_column(INTEGER, nullable=False)
    optional_flags: Mapped[Optional[CustomFlags]] = mapped_column(INTEGER, nullable=True)
    parent: Mapped["ParentClass"] = relationship(back_populates="children")


class IntExtension(int):
    pass


class FurtherIntExtension(IntExtension):
    pass


class StringExtension(str):
    pass


class ChildXmlClass(BaseXmlModelWithNS):
    childInt: IntExtension = element()
    childList: Optional[list[str]] = element()


class SiblingXmlClass(BaseXmlModelWithNS):
    siblingStr: StringExtension = element()


class XmlClass(BaseXmlModelWithNS):
    myInt: Optional[FurtherIntExtension] = element()
    myStr: StringExtension = element()
    myChildren: list[ChildXmlClass] = element()
    mySibling: SiblingXmlClass = element()


class FurtherXmlClass(XmlClass):
    myOtherInt: IntExtension = element()


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


def test_get_generatable_class_base():
    assert get_generatable_class_base(ParentClass) == Base
    assert get_generatable_class_base(ChildClass) == Base
    assert get_generatable_class_base(XmlClass) == BaseXmlModel
    assert get_generatable_class_base(FurtherXmlClass) == BaseXmlModel
    assert get_generatable_class_base(ChildXmlClass) == BaseXmlModel
    assert get_generatable_class_base(Optional[ChildXmlClass]) == BaseXmlModel
    assert get_generatable_class_base(Optional[FurtherXmlClass]) == BaseXmlModel

    assert get_generatable_class_base(str) is None
    assert get_generatable_class_base(FurtherIntExtension) is None
    assert get_generatable_class_base(Optional[str]) is None
    assert get_generatable_class_base(Optional[FurtherIntExtension]) is None


def test_get_optional_type_argument():
    assert get_optional_type_argument(Optional[datetime]) == datetime
    assert get_optional_type_argument(Optional[int]) == int
    assert get_optional_type_argument(Optional[str]) == str
    assert get_optional_type_argument(Union[type(None), str]) == str
    assert get_optional_type_argument(Union[str, type(None)]) == str
    assert get_optional_type_argument(Mapped[Optional[str]]) == str

    assert get_optional_type_argument(ParentClass) is None
    assert get_optional_type_argument(ChildClass) is None
    assert get_optional_type_argument(Union[int, str]) is None


def test_is_optional_type():
    assert is_optional_type(Optional[datetime])
    assert is_optional_type(Optional[int])
    assert is_optional_type(Optional[str])
    assert is_optional_type(Union[type(None), str])
    assert is_optional_type(Union[str, type(None)])
    assert is_optional_type(Mapped[Optional[str]])

    assert not is_optional_type(ParentClass)
    assert not is_optional_type(ChildClass)
    assert not is_optional_type(Union[int, str])


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
    assert is_generatable_type(IntExtension)
    assert is_generatable_type(FurtherIntExtension)
    assert is_generatable_type(StringExtension)
    assert is_generatable_type(CustomFlags)
    assert is_generatable_type(Optional[CustomFlags])
    assert is_generatable_type(Mapped[CustomFlags])
    assert is_generatable_type(Optional[int])
    assert is_generatable_type(Optional[FurtherIntExtension])
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
    """Enumerating a ton of test cases in order to provide certainty about the behaviour of this function (especially
    when dealing with some complex generic type combos)"""

    # With include_optional enabled
    assert get_first_generatable_primitive(int, include_optional=True) == int
    assert get_first_generatable_primitive(datetime, include_optional=True) == datetime
    assert get_first_generatable_primitive(str, include_optional=True) == str
    assert get_first_generatable_primitive(IntExtension, include_optional=True) == int
    assert get_first_generatable_primitive(FurtherIntExtension, include_optional=True) == int
    assert get_first_generatable_primitive(StringExtension, include_optional=True) == str
    assert get_first_generatable_primitive(CustomFlags, include_optional=True) == int
    assert get_first_generatable_primitive(Optional[int], include_optional=True) == Optional[int]
    assert get_first_generatable_primitive(Optional[FurtherIntExtension], include_optional=True) == Optional[int]
    assert get_first_generatable_primitive(Union[int, str], include_optional=True) == int
    assert get_first_generatable_primitive(Union[Optional[str], int], include_optional=True) == Optional[str]
    assert get_first_generatable_primitive(Mapped[str], include_optional=True) == str
    assert get_first_generatable_primitive(Mapped[Optional[str]], include_optional=True) == Optional[str]
    assert get_first_generatable_primitive(Mapped[Optional[Union[str, int]]], include_optional=True) == Optional[str]
    assert (
        get_first_generatable_primitive(Mapped[Optional[Union[StringExtension, int]]], include_optional=True)
        == Optional[str]
    )

    assert get_first_generatable_primitive(Mapped[ParentClass], include_optional=True) is None
    assert get_first_generatable_primitive(ParentClass, include_optional=True) is None
    assert get_first_generatable_primitive(list[str], include_optional=True) is None
    assert get_first_generatable_primitive(list[int], include_optional=True) is None
    assert get_first_generatable_primitive(Mapped[list[str]], include_optional=True) is None

    # With include_optional disabled
    assert get_first_generatable_primitive(int, include_optional=False) == int
    assert get_first_generatable_primitive(datetime, include_optional=False) == datetime
    assert get_first_generatable_primitive(str, include_optional=False) == str
    assert get_first_generatable_primitive(IntExtension, include_optional=False) == int
    assert get_first_generatable_primitive(FurtherIntExtension, include_optional=False) == int
    assert get_first_generatable_primitive(StringExtension, include_optional=False) == str
    assert get_first_generatable_primitive(CustomFlags, include_optional=False) == int
    assert get_first_generatable_primitive(Optional[int], include_optional=False) == int
    assert get_first_generatable_primitive(Optional[FurtherIntExtension], include_optional=False) == int
    assert get_first_generatable_primitive(Union[int, str], include_optional=False) == int
    assert get_first_generatable_primitive(Union[Optional[str], int], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[str], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[Optional[str]], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[Optional[Union[str, int]]], include_optional=False) == str
    assert get_first_generatable_primitive(Mapped[Optional[Union[StringExtension, int]]], include_optional=False) == str

    assert get_first_generatable_primitive(Mapped[ParentClass], include_optional=False) is None
    assert get_first_generatable_primitive(ParentClass, include_optional=False) is None
    assert get_first_generatable_primitive(list[str], include_optional=False) is None
    assert get_first_generatable_primitive(list[int], include_optional=False) is None
    assert get_first_generatable_primitive(Mapped[list[str]], include_optional=False) is None


def test_generate_xml_basic_values():
    p1: FurtherXmlClass = generate_class_instance(FurtherXmlClass)

    assert p1.myInt is not None
    assert p1.myOtherInt is not None
    assert p1.myStr is not None
    assert p1.myChildren is not None and len(p1.myChildren) == 0, "generate_relationships is False"
    assert p1.mySibling is None, "generate_relationships is False so this should not populate"
    assert p1.myInt != p1.myOtherInt, "Checking that fields of the same type get unique values"

    # create a new instance with a different seed
    p2: FurtherXmlClass = generate_class_instance(FurtherXmlClass, seed=123)

    assert p2.myInt is not None
    assert p2.myOtherInt is not None
    assert p2.myStr is not None
    assert p2.myChildren is not None and len(p1.myChildren) == 0, "generate_relationships is False"
    assert p2.mySibling is None, "generate_relationships is False so this should not populate"
    assert p2.myInt != p2.myOtherInt, "Checking that fields of the same type get unique values"

    assert p1.myInt != p2.myInt, "Checking that different seed numbers yields different results"
    assert p1.myOtherInt != p2.myOtherInt, "Checking that different seed numbers yields different results"
    assert p1.myStr != p2.myStr, "Checking that different seed numbers yields different results"

    p3: FurtherXmlClass = generate_class_instance(FurtherXmlClass, seed=456, optional_is_none=True)
    assert p3.myInt is None, "This field is optional and optional_is_none=True"
    assert p3.myOtherInt is not None
    assert p3.myStr is not None
    assert p3.myChildren is not None and len(p1.myChildren) == 0, "generate_relationships is False"
    assert p3.mySibling is None, "generate_relationships is False so this should not populate"


def test_generate_xml_instance_relationships():
    p1: FurtherXmlClass = generate_class_instance(FurtherXmlClass, generate_relationships=True)
    assert p1.myChildren is not None and len(p1.myChildren) == 1 and isinstance(p1.myChildren[0], ChildXmlClass)
    assert p1.mySibling is not None and isinstance(p1.mySibling, SiblingXmlClass)

    p2: FurtherXmlClass = generate_class_instance(FurtherXmlClass, seed=112, generate_relationships=True)
    assert p2.myChildren is not None and len(p2.myChildren) == 1 and isinstance(p2.myChildren[0], ChildXmlClass)
    assert p2.mySibling is not None and isinstance(p2.mySibling, SiblingXmlClass)

    assert p1.myChildren[0].childInt != p2.myChildren[0].childInt, "Differing seed values generate different results"
    assert p1.myChildren[0].childList != p2.myChildren[0].childList, "Differing seed values generate different results"
    assert p1.mySibling.siblingStr != p2.mySibling.siblingStr, "Differing seed values generate different results"


def test_generate_sql_alchemy_instance_basic_values():
    """Simple sanity check on some models to make sure the basic assumptions of generate_sql_alchemy_instance hold"""

    c1: ChildClass = generate_class_instance(ChildClass)

    # Ensure we create values
    assert c1.name is not None
    assert c1.long_name is not None
    assert c1.child_id is not None
    assert c1.parent_id is not None
    assert c1.created_at is not None
    assert c1.deleted_at is not None
    assert c1.flags is not None
    assert c1.optional_flags is not None
    assert c1.parent is None, "generate_relationships is False so this should not populate"

    assert c1.name != c1.long_name, "Checking that fields of the same type get unique values"
    assert c1.child_id != c1.parent_id, "Checking that fields of the same type get unique values"
    assert c1.created_at != c1.deleted_at, "Checking that fields of the same type get unique values"
    assert c1.flags != c1.optional_flags, "Checking that fields of the same type get unique values"

    # create a new instance with a different seed
    c2: ChildClass = generate_class_instance(ChildClass, seed=123)
    assert c2.name is not None
    assert c2.long_name is not None
    assert c2.child_id is not None
    assert c2.parent_id is not None
    assert c2.created_at is not None
    assert c2.deleted_at is not None
    assert c2.flags is not None
    assert c2.optional_flags is not None
    assert c2.parent is None, "generate_relationships is False so this should not populate"

    assert c2.name != c2.long_name, "Checking that fields of the same type get unique values"
    assert c2.child_id != c2.parent_id, "Checking that fields of the same type get unique values"
    assert c2.created_at != c2.deleted_at, "Checking that fields of the same type get unique values"
    assert c2.flags != c2.optional_flags, "Checking that fields of the same type get unique values"

    # validate that c1 != c2
    assert c1.name != c2.name, "Checking that different seed numbers yields different results"
    assert c1.long_name != c2.long_name, "Checking that different seed numbers yields different results"
    assert c1.child_id != c2.child_id, "Checking that different seed numbers yields different results"
    assert c1.parent_id != c2.parent_id, "Checking that different seed numbers yields different results"
    assert c1.created_at != c2.created_at, "Checking that different seed numbers yields different results"
    assert c1.deleted_at != c2.deleted_at, "Checking that different seed numbers yields different results"
    assert c1.flags != c2.flags, "Checking that different seed numbers yields different results"
    assert c1.optional_flags != c2.optional_flags, "Checking that different seed numbers yields different results"

    # check optional_is_none
    c3: ChildClass = generate_class_instance(ChildClass, seed=456, optional_is_none=True)
    assert c3.name is not None
    assert c3.long_name is None, "optional_is_none is True and this is optional"
    assert c3.child_id is not None
    assert c3.parent_id is not None
    assert c3.parent is None, "generate_relationships is False so this should not populate"
    assert c3.created_at is not None
    assert c3.deleted_at is None, "optional_is_none is True and this is optional"
    assert c3.flags is not None
    assert c3.optional_flags is None, "optional_is_none is True and this is optional"


def test_generate_sql_alchemy_instance_single_relationships():
    """Sanity check that relationships can be generated as demanded"""

    c1: ChildClass = generate_class_instance(ChildClass, generate_relationships=True)

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

    c2: ChildClass = generate_class_instance(ChildClass, seed=2, generate_relationships=True)
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

    p1: ParentClass = generate_class_instance(ParentClass, generate_relationships=True)

    assert (
        p1.children is not None and len(p1.children) == 1
    ), "generate_relationships is True so this should be populated"
    assert isinstance(p1.children[0], ChildClass)
    assert p1.children[0].child_id is not None
    assert p1.children[0].name is not None
    assert p1.children[0].long_name is not None
    assert p1.children[0].created_at is not None
    assert p1.children[0].deleted_at is not None
    assert p1.children[0].parent is not None and p1.children[0].parent == p1, "Backreference should self reference"
    assert (
        p1.children[0].created_at != p1.children[0].deleted_at
    ), "Checking that fields of the same type get unique values"
    assert p1.children[0].long_name != p1.children[0].name, "Checking that fields of the same type get unique values"

    p2: ParentClass = generate_class_instance(ParentClass, seed=2, generate_relationships=True)
    assert isinstance(p2.children[0], ChildClass)
    assert p2.children[0].child_id is not None
    assert p2.children[0].name is not None
    assert p2.children[0].long_name is not None
    assert p2.children[0].created_at is not None
    assert p2.children[0].deleted_at is not None
    assert p2.children[0].parent is not None and p2.children[0].parent == p2, "Backreference should self reference"
    assert (
        p2.children[0].created_at != p2.children[0].deleted_at
    ), "Checking that fields of the same type get unique values"
    assert p2.children[0].long_name != p2.children[0].name, "Checking that fields of the same type get unique values"
    assert (
        p1.children[0].created_at != p2.children[0].created_at
    ), "Checking that different seed numbers yields different results"
    assert (
        p1.children[0].deleted_at != p2.children[0].deleted_at
    ), "Checking that different seed numbers yields different results"


def test_clone_class_instance_sql_alchemy():
    """Check that cloned sql alchemy classes are properly shallow cloned"""
    original: ParentClass = generate_class_instance(ParentClass, generate_relationships=True)
    clone: ParentClass = clone_class_instance(original)

    assert clone
    assert clone is not original
    assert type(clone) == ParentClass

    assert clone.parent_id is original.parent_id
    assert clone.name is original.name
    assert clone.created is original.created
    assert clone.deleted is original.deleted
    assert clone.disabled is original.disabled
    assert clone.total is original.total


def test_clone_class_instance_xml():
    """Check that cloned xml classes are properly shallow cloned"""
    original: FurtherXmlClass = generate_class_instance(FurtherXmlClass, generate_relationships=True)
    clone: FurtherXmlClass = clone_class_instance(original)

    assert clone
    assert clone is not original
    assert type(clone) == FurtherXmlClass

    assert clone.myInt is original.myInt
    assert clone.myStr is original.myStr
    assert clone.myChildren is original.myChildren
    assert clone.mySibling is original.mySibling
    assert clone.myOtherInt is original.myOtherInt
