import inspect
from typing import get_type_hints

import pytest
from assertical.fake.generator import (
    BASE_CLASS_PUBLIC_MEMBERS,
    CLASS_MEMBER_FETCHERS,
    get_generatable_class_base,
    is_member_public,
    is_optional_type,
)
from sqlalchemy.orm import MappedColumn

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

        type_hint_optional = is_optional_type(member_type)
        sql_orm_nullable = getattr(mapped_column_details, "nullable", None)
        if sql_orm_nullable is not None and type_hint_optional != sql_orm_nullable:
            errors.append(
                f"{member_name} has type hint {member_type} but has sqlalchemy ORM nullable {sql_orm_nullable}"
            )

    assert not errors, "\n".join(errors)
