import inspect
from typing import get_type_hints

import pytest
from assertical.fake.generator import (
    BASE_CLASS_PUBLIC_MEMBERS,
    CLASS_MEMBER_FETCHERS,
    get_generatable_class_base,
    is_generatable_type,
    is_member_public,
    is_optional_type,
    remove_passthrough_type,
)
from sqlalchemy.orm import ColumnProperty, MappedColumn

import envoy.server.model as all_models
from envoy.server.model import Base


@pytest.mark.parametrize(
    "model_type", [t for (name, t) in inspect.getmembers(all_models, inspect.isclass) if issubclass(t, Base)]
)
def test_validate_model_definitions(model_type: type):
    """Runs some high level reflection checks on all model types to look for things that are "off" """
    base = get_generatable_class_base(model_type)
    type_hints = get_type_hints(model_type)

    errors: list[str] = []
    for member_name in CLASS_MEMBER_FETCHERS[base](model_type):
        if not is_member_public(member_name):
            continue
        if member_name in BASE_CLASS_PUBLIC_MEMBERS[base]:
            continue

        mapped_column_details: MappedColumn = getattr(model_type, member_name)

        if member_name not in type_hints:
            errors.append(f"{member_name} is missing a type hint")
            continue

        member_type = type_hints[member_name]

        # Check the type is "simple" and that we haven't accidentally typed it with some complex type
        if isinstance(mapped_column_details.property, ColumnProperty):
            # We have a "simple type" that sqlalchemy has mapped into a column
            if not is_generatable_type(member_type):
                # And then the typehint doesn't appear to be simple. Is the type hint appropriate?
                errors.append(
                    f"'{member_name}' has type hint '{member_type}' that appears incorrect. "
                    + "The type appears to be a non primitive type but the property is NOT a ORM relationship"
                )

        # Check nullability
        type_hint_optional = is_optional_type(member_type)
        sql_orm_nullable = getattr(mapped_column_details, "nullable", None)
        if sql_orm_nullable is not None and type_hint_optional != sql_orm_nullable:
            errors.append(
                f"{member_name} has type hint {member_type} but has sqlalchemy ORM nullable {sql_orm_nullable}"
            )

    assert not errors, "\n".join(errors)
