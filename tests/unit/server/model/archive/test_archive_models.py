import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Generator, Optional

import pytest
from assertical.asserts.type import assert_set_type
from assertical.fake.generator import PropertyGenerationDetails, enumerate_class_properties, get_enum_type
from sqlalchemy.orm.attributes import InstrumentedAttribute

from envoy.server.model.archive.base import ARCHIVE_BASE_COLUMNS, ARCHIVE_TABLE_PREFIX, ARCHIVE_TYPE_PREFIX, ArchiveBase
from envoy.server.model.base import Base

MODELS_PACKAGE = "envoy.server.model"
ARCHIVE_PACKAGE = "envoy.server.model.archive"

ARCHIVE_BASE_MEMBERS: set[str] = {p.name for p in enumerate_class_properties(ArchiveBase)}


def find_submodules(module_path: str) -> set[str]:
    """Finds all submodules that are immediately below the specified module_path"""
    models_module = importlib.import_module(module_path)
    models_dir = Path(models_module.__file__).parent
    return {modname for _, modname, ispkg in pkgutil.iter_modules([str(models_dir)]) if not ispkg}


def find_paired_unpaired_archive_modules() -> set[tuple[Optional[str], Optional[str]]]:
    """Finds modules from the models/archive packages that have the same name.

    Returns a list of these pairs in the form of (model_module, archive_module)

    If a module exists on only one side, it will be returned with the other side being None"""

    models_submodules = find_submodules(MODELS_PACKAGE)
    archive_submodules = find_submodules(ARCHIVE_PACKAGE)

    result: set[tuple[Optional[str], Optional[str]]] = set()
    for a in archive_submodules:
        if a in models_submodules:
            result.add((MODELS_PACKAGE + "." + a, ARCHIVE_PACKAGE + "." + a))
        else:
            result.add((None, ARCHIVE_PACKAGE + "." + a))

    for m in models_submodules:
        if m in archive_submodules:
            result.add((MODELS_PACKAGE + "." + m, ARCHIVE_PACKAGE + "." + m))
        else:
            result.add((MODELS_PACKAGE + "." + m, None))

    return result


def find_paired_archive_modules() -> list[tuple[str, str]]:
    """Finds modules from the models/archive packages that have the same name.

    Returns a list of these pairs in the form of (model_module, archive_module)"""

    pairings: list[tuple[str, str]] = []
    for m, a in find_paired_unpaired_archive_modules():

        if m is None or a is None:
            continue

        if "base" in m or "base" in a:
            continue
        pairings.append((m, a))
    return pairings


def find_paired_unpaired_archive_classes() -> set[Optional[type], Optional[type]]:
    """Enumerates submodules from find_paired_archive_modules and identifies classes from
    each pairing that have the same name. Returns the paired types (or None if unpaired)

    Noting that a model class like Site will be prefixed on the archive side as ArchiveSite"""
    pairings: set[Optional[type], Optional[type]] = set()
    for m, a in find_paired_archive_modules():

        model_types_by_name: dict[str, type] = dict(
            (t.__name__, t)
            for _, t in inspect.getmembers(importlib.import_module(m), inspect.isclass)
            if t.__module__ == m
        )
        archive_types_by_name: dict[str, type] = dict(
            (t.__name__, t)
            for _, t in inspect.getmembers(importlib.import_module(a), inspect.isclass)
            if t.__module__ == a
        )

        for model_name, mt in model_types_by_name.items():
            archive_name = ARCHIVE_TYPE_PREFIX + model_name
            if archive_name in archive_types_by_name:
                pairings.add((mt, archive_types_by_name[archive_name]))
            else:
                pairings.add((mt, None))

        for archive_name, at in archive_types_by_name.items():
            model_name = archive_name[len(ARCHIVE_TYPE_PREFIX) :]  # noqa: E203
            if model_name not in model_types_by_name:
                pairings.add((None, at))

    return pairings


def find_paired_archive_classes() -> list[tuple[type, type]]:
    """Returns a list of types from the archive submodule paired with the "same" type from the original models
    submodule.

    returns (model_type, archive_type)

    It's expected that all archive classes will map to a corresponding model type"""
    pairings: list[tuple[type, type]] = []
    for m, a in find_paired_unpaired_archive_classes():

        if m is None or a is None:
            continue
        pairings.append((m, a))

    # We sort so that we have a deterministic test ordering
    return list(sorted(pairings, key=lambda t: t[0].__name__ + t[1].__name__))


def test_archive_base_columns():
    assert_set_type(str, ARCHIVE_BASE_COLUMNS)
    assert len(ARCHIVE_BASE_COLUMNS) > 0
    for c in ARCHIVE_BASE_COLUMNS:
        assert hasattr(ArchiveBase, c)


def test_find_paired_archive_modules():
    """Sanity checks find_paired_archive_modules"""
    items = find_paired_archive_modules()
    assert len(items) != 0
    assert all((m[0].startswith(MODELS_PACKAGE) for m in items))
    assert all((m[1].startswith(ARCHIVE_PACKAGE) for m in items))
    assert all(("base" not in m[0] for m in items))
    assert all(("base" not in m[1] for m in items))


def test_all_archive_modules_pair():
    """Catches errors where a submodule of the archive package doesn't have the same name as a submodule of the
    models package"""
    for m, a in find_paired_unpaired_archive_modules():
        assert m is not None, f"Archive module {a} doesn't map to a module in {MODELS_PACKAGE}. Maybe a file name typo?"


def test_all_archive_classes_pair():
    """Catches errors where a class in an archive submodule doesn't map to a class in a model submodule"""
    for m, a in find_paired_unpaired_archive_classes():
        assert m is not None, f"Archive class {a} doesn't pair with a type in {MODELS_PACKAGE}."


def test_find_paired_archive_classes():
    items = find_paired_archive_classes()
    assert len(items) != 0


@pytest.mark.parametrize("model_type, archive_type", find_paired_archive_classes())
def test_archive_models_match_original_basic_schema(model_type: type, archive_type: type):
    """Compares every model with its corresponding archive model.

    THIS WILL TEST:
    * Column names in archive/source are matching (no type interrogation)
    * Table names "match"

    Other tests in this module will handle cases where there is an unpaired model"""

    # Check correct subclassing
    assert issubclass(model_type, Base)
    assert not issubclass(model_type, ArchiveBase)
    assert issubclass(archive_type, ArchiveBase)

    # Check tablename is the same (minus the ARCHIVE_TABLE_PREFIX)
    assert archive_type.__tablename__.startswith(ARCHIVE_TABLE_PREFIX)
    assert (
        model_type.__tablename__
        and model_type.__tablename__ == archive_type.__tablename__[len(ARCHIVE_TABLE_PREFIX) :]  # noqa: E203
    )

    errors: list[str] = []

    # Check the various members line up. We're comparing non relationship columns on the model side
    # against the non "archive" columns on the archive side
    model_members_by_name = dict(
        (p.name, p)
        for p in enumerate_class_properties(model_type)
        if p.is_primitive_type or get_enum_type(p.type_to_generate, False) is not None
    )
    archive_members_by_name = dict(
        (p.name, p) for p in enumerate_class_properties(archive_type) if p.name not in ARCHIVE_BASE_MEMBERS
    )
    if model_members_by_name.keys() != archive_members_by_name.keys():
        # Pretty print out the errors
        for model_member in model_members_by_name.keys():
            if model_member not in archive_members_by_name:
                errors.append(f"Column '{model_member}' from {model_type} is NOT found in {archive_type}")
        for archive_member in archive_members_by_name.keys():
            if archive_member not in model_members_by_name:
                errors.append(f"Column '{archive_member}' from {archive_type} doesn't map to anything in {model_type}")
    assert not errors, "\n".join(errors)
    assert len(model_members_by_name) == len(archive_members_by_name)


def enumerate_paired_columns(
    model_type: type, archive_type: type
) -> Generator[tuple[str, PropertyGenerationDetails, PropertyGenerationDetails], None, None]:
    """Enumerates the "same" columns from a model type and archive type and returns them as a series of tuples. If there
    is a column mismatch test_archive_models_match_original_basic_schema will cover it - this *may* raise Exceptions
    if test_archive_models_match_original_basic_schema has failing test cases.

    Returns
        (column_name: str, model_property: PropertyGenerationDetails, archive_property: PropertyGenerationDetails)"""
    model_members_by_name = dict(
        (p.name, p)
        for p in enumerate_class_properties(model_type)
        if p.is_primitive_type or get_enum_type(p.type_to_generate, False) is not None
    )
    archive_members_by_name = dict(
        (p.name, p) for p in enumerate_class_properties(archive_type) if p.name not in ARCHIVE_BASE_MEMBERS
    )
    for col_name, model_prop in model_members_by_name.items():
        archive_prop = archive_members_by_name.get(col_name, None)
        if archive_prop is None:
            raise Exception(
                f"{archive_type} doesn't have {col_name}. See test_archive_models_match_original_basic_schema"
            )

        yield (col_name, model_prop, archive_prop)


@pytest.mark.parametrize("model_type, archive_type", find_paired_archive_classes())
def test_archive_models_match_original_type_hints(model_type: type, archive_type: type):
    """Compares every model with its corresponding archive model.

    This test is ONLY valid if all cases in test_archive_models_match_original_basic_schema are passing

    THIS WILL TEST:
    * Type hints in model/archive types align

    Other tests in this module will handle cases where there is an unpaired model"""
    errors = []
    for col_name, model_prop, archive_prop in enumerate_paired_columns(
        model_type=model_type, archive_type=archive_type
    ):
        if archive_prop.type_to_generate != model_prop.type_to_generate:
            errors.append(
                f"Property '{col_name}' has a mismatching type hint between the archive and model version."
                + f"{archive_prop.type_to_generate} != {model_prop.type_to_generate}"
            )
            continue

        if archive_prop.is_optional != model_prop.is_optional:
            errors.append(
                f"Property '{col_name}' has a mismatching type hint (Optional vs not Optional) between versions."
            )
            continue

    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("model_type, archive_type", find_paired_archive_classes())
def test_archive_models_match_original_db_definitions(model_type: type, archive_type: type):
    """Compares every model with its corresponding archive model.

    This test is ONLY valid if all cases in test_archive_models_match_original_basic_schema are passing

    THIS WILL TEST:
    * Database schema definitions in model/archive types are in sync (eg Column name, DB type etc)

    Other tests in this module will handle cases where there is an unpaired model"""
    errors = []
    for col_name, _, _ in enumerate_paired_columns(model_type=model_type, archive_type=archive_type):
        model_db: InstrumentedAttribute = getattr(model_type, col_name)
        archive_db: InstrumentedAttribute = getattr(archive_type, col_name)

        if model_db.name != archive_db.name:
            errors.append(f"Property '{col_name}' mismatching column name: '{model_db.name}' != '{archive_db.name}'")
            continue

        if len(archive_db.foreign_keys) != 0:
            errors.append(f"Property '{col_name}' has a ForeignKey in the archive version.")
            continue

        if archive_db.index:
            if not model_db.primary_key:
                errors.append(f"Property '{col_name}' has an index. Only archived primary keys should be indexed.")
                continue

        if archive_db.server_default:
            errors.append(
                f"Property '{col_name}' has a server_default in the archive version. "
                + "No defaults should be necessary as all column values will be copied from their source"
            )
            continue

        if archive_db.unique:
            errors.append(
                f"Property '{col_name}' has unique attribute set in the archive version. "
                + "Unique does NOT apply to the archive tables and will generate errors if included."
            )
            continue

        if hasattr(archive_db.property, "order_by"):
            if archive_db.property.order_by:
                errors.append(
                    f"Property '{col_name}' has an order by attribute set in the archive version. "
                    + "Order by attributes should NOT be replicated in the archive."
                )
                continue

        if model_db.nullable != archive_db.nullable:
            errors.append(f"Property '{col_name}' has a mismatch on nullable between the archive and model versions.")
            continue

        # Now compare DB types, unfortunately we can't just ==
        # This method will spit out something like VARCHAR(16) which should be good enough to compare directly
        if hasattr(model_db, "type"):
            if str(model_db.type) != str(archive_db.type):
                errors.append(f"Property '{col_name}' has mismatching DB types. {model_db.type} != {archive_db.type}")
                continue

    assert not errors, "\n".join(errors)
