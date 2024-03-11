import inspect
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from types import NoneType
from typing import Any, Callable, Optional, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel
from pydantic_xml import BaseXmlModel
from sqlalchemy.orm import Mapped

from envoy.server.model.base import Base


@dataclass
class _PlaceholderDataclassBase:
    """Dataclass has no base class - instead we fall back to using this as a placeholder"""


def safe_is_subclass(class_to_check: type, parent_class: type) -> bool:
    try:
        return issubclass(class_to_check, parent_class)
    except TypeError:
        # This is working around some quirks with Python
        # eg - issubclass(list[int], ParentClass) will return False
        #      issubclass(typing.List[int], ParentClass) will raise a TypeError
        #      issubclass(Optional[int], ParentClass) will raise a TypeError
        return False


def get_enum_type(t: Optional[type], include_optional: bool) -> Optional[type]:
    """If t is an enum type (ignoring Optional/Passthrough types) - return the underlying
    subclass of Enum. Otherwise return None. include_optional = True will cause any Optional[] wrappers around the
    enum type to be returned - otherwise just the raw enum_type will be returned


    Eg get_enum_type(Mapped[Optional[MyIntEnum]], False) will return MyIntEum
    Eg get_enum_type(Mapped[Optional[MyIntEnum]], True) will return Optional[MyIntEum]
    Eg get_enum_type(MyIntEum, False) will return MyIntEum
    Eg get_enum_type(MyIntEum, True) will return MyIntEum
    Eg get_enum_type(Mapped[int], True) will return None
    """
    if t is None:
        return None

    if is_passthrough_type(t):
        t = remove_passthrough_type(t)

    # If t is Optional[MyEnum] or just MyEnum - inner_enum_type will be MyEnum in either case
    inner_enum_type = t
    optional = False
    if is_optional_type(t):
        optional = True
        inner_enum_type = get_optional_type_argument(t)
        assert inner_enum_type is not None

    is_union = get_origin(t) == Union and len([a for a in get_args(t) if a is not NoneType]) > 1
    if is_union:
        for union_arg in get_args(t):
            arg_enum = get_enum_type(union_arg, include_optional)
            if arg_enum is not None:
                if optional and include_optional:
                    return Optional[arg_enum]
                else:
                    return arg_enum
    elif safe_is_subclass(inner_enum_type, Enum):
        if include_optional:
            return t
        else:
            return inner_enum_type

    return None


def generate_value(t: type, seed: int = 1, optional_is_none: bool = False) -> Any:
    """Generates a seeded value based on the specified type. Throws an exception if it's not matched

    Feel free to expand this to new types as they come about"""
    if optional_is_none and is_optional_type(t):
        return None

    primitive_type = get_first_generatable_primitive(t, include_optional=False)

    # Enums are treated as a unique generation case - these are picked from the set of all possible enum vals
    enum_t = get_enum_type(t, False)
    if enum_t is not None:
        enum_values = list(enum_t)
        return enum_values[seed % len(enum_values)]

    if primitive_type not in PRIMITIVE_VALUE_GENERATORS:
        raise Exception(f"Unsupported type {t} for seed {seed}")

    return PRIMITIVE_VALUE_GENERATORS[primitive_type](seed)


def get_first_generatable_primitive(t: type, include_optional: bool) -> Optional[type]:
    """Given a primitive type - return that type. Given a generic type, walk any union arguments looking for a
    primitive type

    if the type is optional and include_optional is True - the Optional[type] will be returned, otherwise just the type
    argument will be returned

    Types that inherit directly from a primitive type will be returned as the base primitive type

    Otherwise return None"""

    # if we can generate the type out of the box - we're done
    if t in PRIMITIVE_VALUE_GENERATORS:
        return t

    # if type is an enum - we generate this differently
    enum_t = get_enum_type(t, include_optional)
    if enum_t is not None:
        return enum_t

    # Check if the type is an extension of a primitive type
    if hasattr(t, "__bases__"):  # we need this check as types like Optional don't have this property
        for base in inspect.getmro(t):
            if base in PRIMITIVE_VALUE_GENERATORS:
                return base

    # certain types will just pass through looking at the arguments
    # eg: Mapped[Optional[int]] is really just Optional[int] for this function's purposes
    if is_passthrough_type(t):
        return get_first_generatable_primitive(remove_passthrough_type(t), include_optional=include_optional)

    # If we have an Optional[type] (which resolves to Union[NoneType, type]) we need to be careful about how we
    # extract the type
    origin_type = get_origin(t)
    include_optional_type = include_optional and is_optional_type(t)
    if origin_type == Union:
        for union_arg in get_args(t):
            prim_type = get_first_generatable_primitive(union_arg, include_optional=False)
            if prim_type is not None:
                return Optional[prim_type] if include_optional_type else prim_type

    return None


def is_passthrough_type(t: type) -> bool:
    """This is for catching types like Mapped[int] which mainly just decorate the generic type argument
    without providing any useful information for the purposes of simple reading/writing values"""
    return get_origin(t) == Mapped


def remove_passthrough_type(t: type) -> type:
    """Given a generic PassthroughType[t] (identified by is_passthrough_type) - return t"""
    while is_passthrough_type(t):
        t = get_args(t)[0]
    return t


def is_generatable_type(t: type) -> bool:
    """Returns true if the type is generatable using generate_value (essentially is it a primitive type)"""
    primitive_type = get_first_generatable_primitive(t, include_optional=False)
    if get_enum_type(primitive_type, False) is not None:
        return True  # Enums are a special case
    return primitive_type in PRIMITIVE_VALUE_GENERATORS


def get_generatable_class_base(t: type) -> Optional[type]:
    """Given a class - look to see if it inherits from a key CLASS_INSTANCE_GENERATORS and return that key
    otherwise return None"""
    target_type = remove_passthrough_type(t)

    # we don't consider the Optional[MyType] - only the MyType
    optional_arg = get_optional_type_argument(target_type)
    if optional_arg is not None:
        target_type = optional_arg

    if not inspect.isclass(target_type):
        return None

    for base_class in inspect.getmro(target_type):
        if base_class in CLASS_INSTANCE_GENERATORS:
            return base_class

    # check for dataclass
    for base_class in inspect.getmro(target_type):
        if is_dataclass(base_class):
            return _PlaceholderDataclassBase

    return None


def get_optional_type_argument(t: type) -> Optional[type]:
    """If t is Optional[MyType] - return MyType - otherwise return None.

    If None is returned then t is NOT an optional type"""
    target_type = remove_passthrough_type(t)
    if get_origin(target_type) != Union:
        return None

    # is this an Optional union?
    type_args = get_args(target_type)
    if type(None) not in type_args:
        return None

    # get the first non None type
    return [arg for arg in type_args if arg is not NoneType][0]


def is_optional_type(t: type) -> bool:
    """Returns true if t is an Optional type"""
    return get_optional_type_argument(t) is not None


def is_member_public(member_name: str) -> bool:
    """Simple heuristic to test if a member is public (True) or private/internal (False)"""
    return len(member_name) > 0 and member_name[0] != "_"


def generate_class_instance(  # noqa: C901
    t: type,
    seed: int = 1,
    optional_is_none: bool = False,
    generate_relationships: bool = False,
    visited_types_with_sources: Optional[dict[type, list[Optional[tuple[str, type]]]]] = None,
    source_variable: Optional[tuple[str, type]] = None,
) -> Any:
    """Given a child class of a key to CLASS_INSTANCE_GENERATORS - generate an instance of that class
    with all properties being assigned unique values based off of seed. The values will match type hints

    Any "private" members beginning with '_' will be skipped

    generate_relationships will recursively generate relationships generating instances as required. (SQL ALchemy
    will handle assigning backreferences too)

    If the type cannot be instantiated due to missing type hints / other info exceptions will be raised

    visited_types_with_sources should not be specified - it's for internal use only
    source_variable should not be specified - it's for internal use only"""
    t = remove_passthrough_type(t)

    # stop back references from infinite looping
    if visited_types_with_sources is None:
        visited_types_with_sources = {}
    sources = visited_types_with_sources.get(t, None)
    if sources and (None in sources or source_variable in sources):
        # If we've looped back to the original type OR we've visited this type from the same source - abort!
        # Same source being the same member from the same type
        return None
    if sources is None:
        visited_types_with_sources[t] = sources = []
    sources.append(source_variable)

    # We can only generate class instances of classes that inherit from a known base
    t_generatable_base = get_generatable_class_base(t)
    if t_generatable_base is None:
        raise Exception(f"Type {t} does not inherit from one of {CLASS_INSTANCE_GENERATORS.keys()}")

    type_hints = get_type_hints(t)

    # We will be creating a dict of property names and their generated values
    # Those values can be basic primitive values or optionally populated
    current_seed = seed
    values: dict[str, Any] = {}
    for member_name in CLASS_MEMBER_FETCHERS[t_generatable_base](t):
        # Skip members that are private OR that are public members of the base class
        if not is_member_public(member_name):
            continue
        if member_name in BASE_CLASS_PUBLIC_MEMBERS[t_generatable_base]:
            continue

        if member_name not in type_hints:
            raise Exception(f"Type {t} has property {member_name} that is missing a type hint")

        # We generate lists the same as single values (we just wrap the results in a list)
        # keep track of the list state / element type before generating
        member_type = remove_passthrough_type(type_hints[member_name])
        optional_arg_type = get_optional_type_argument(member_type)
        is_optional = optional_arg_type is not None
        is_list = False
        if is_optional:
            is_list = get_origin(optional_arg_type) == list
        else:
            is_list = get_origin(member_type) == list
        empty_list: bool = False  # if True - use an empty list
        if is_list:
            member_type = get_args(optional_arg_type)[0] if is_optional else get_args(member_type)[0]

        # This is an SQL Alchemy specific quirk - hopefully we don't need too many of these special cases
        #
        # if we are passed a string name of a type (such as SQL Alchemy relationships are want to do)
        # eg - list["ChildType"] we need to be able to resolve that
        # Currently we're digging around in the guts of the Base registry - there might be an official way to do this
        # but I haven't yet figured it out.
        if t_generatable_base == Base:
            if isinstance(member_type, str):
                member_type = Base.registry._class_registry[member_type]

        generated_value: Any = None
        if is_generatable_type(member_type):
            primitive_type = get_first_generatable_primitive(member_type, include_optional=True)
            generated_value = generate_value(primitive_type, seed=current_seed, optional_is_none=optional_is_none)
            current_seed += 1
        elif get_generatable_class_base(member_type) is not None:
            if is_optional and optional_is_none:
                generated_value = None
                is_list = False
            elif generate_relationships:
                relationship_type = optional_arg_type if is_optional else member_type
                generated_value = generate_class_instance(
                    relationship_type,
                    seed=current_seed,
                    optional_is_none=optional_is_none,
                    generate_relationships=generate_relationships,
                    visited_types_with_sources=visited_types_with_sources,
                    source_variable=(member_name, t),
                )

                # None can be generated when Type A has child B that includes a backreference to A. in these
                # circumstances the visited_types short circuit will just return None from generate_class_instance
                # (to stop infinite recursion) The way we handle this is to just generate an empty list (if this is
                # a list entity)
                empty_list = generated_value is None
            else:
                empty_list = True
                generated_value = None
            current_seed += 1000  # Rather than calculating how many seed values were utilised - set it arbitrarily high
        else:
            pretty_type_str = f"list[{member_type}]" if is_list else member_type
            raise Exception(f"Type {t} has property {member_name} with type {pretty_type_str} that cannot be generated")

        if is_list:
            values[member_name] = [] if empty_list else [generated_value]
        else:
            values[member_name] = generated_value

    return CLASS_INSTANCE_GENERATORS[t_generatable_base](t, values)


def clone_class_instance(obj: Any, ignored_properties: Optional[set[str]] = None) -> Any:
    """Given an instance of a child class of a key to CLASS_INSTANCE_GENERATORS - generate a new instance of that class
    using references to the values in the current public properties in obj (i.e. a shallow clone).

    Any public properties belonging to the base class will be skipped (i.e only properties generated by
    generate_class_instance) will

    if ignored_properties is set - any property name in that set will be skipped (not copied)

    Any "private" members beginning with '_' will be skipped"""
    t = type(obj)

    # We can only generate class instances of classes that inherit from a known base
    t_generatable_base = get_generatable_class_base(t)
    if t_generatable_base is None:
        raise Exception(f"Obj {obj} with type {t} does not inherit from one of {CLASS_INSTANCE_GENERATORS.keys()}")

    # We will be creating a dict of property names and their generated values
    # Those values can be basic primitive values or optionally populated
    values: dict[str, Any] = {}
    for member_name in CLASS_MEMBER_FETCHERS[t_generatable_base](t):
        # Skip members that are private OR that are public members of the base class
        if not is_member_public(member_name):
            continue
        if member_name in BASE_CLASS_PUBLIC_MEMBERS[t_generatable_base]:
            continue
        if ignored_properties and member_name in ignored_properties:
            continue

        values[member_name] = getattr(obj, member_name)

    return CLASS_INSTANCE_GENERATORS[t_generatable_base](t, values)


def check_class_instance_equality(
    t: type,
    expected: Any,
    actual: Any,
    ignored_properties: Optional[set[str]] = None,
) -> list[str]:
    """Given a type t and two instances. Run through the public members of t and assert that the values all match up.
    This will only compare properties whose type passes is_generatable_type.

    Any "private" members beginning with '_' will be skipped

    ignored properties are a set of property names that will NOT be asserted for equality

    returns a list of error messages (or an empty list if expected == actual)"""

    if expected is None and actual is None:
        return []

    if expected is None:
        return [f"expected is None but actual is {actual}"]

    if actual is None:
        return [f"actual is None but expected is {expected}"]

    t = remove_passthrough_type(t)

    # We can only generate class instances of classes that inherit from a known base
    t_generatable_base = get_generatable_class_base(t)
    if t_generatable_base is None:
        raise Exception(f"Type {t} does not inherit from one of {CLASS_INSTANCE_GENERATORS.keys()}")

    type_hints = get_type_hints(t)

    # We will be creating a dict of property names and their generated values
    # Those values can be basic primitive values or optionally populated
    error_messages = []
    for member_name in CLASS_MEMBER_FETCHERS[t_generatable_base](t):
        # Skip members that are private OR that are public members of the base class
        if not is_member_public(member_name):
            continue
        if member_name in BASE_CLASS_PUBLIC_MEMBERS[t_generatable_base]:
            continue
        if ignored_properties and member_name in ignored_properties:
            continue

        if member_name not in type_hints:
            raise Exception(f"Type {t} has property {member_name} that is missing a type hint")

        member_type = remove_passthrough_type(type_hints[member_name])
        if not is_generatable_type(member_type):
            continue

        expected_val = getattr(expected, member_name)
        actual_val = getattr(actual, member_name)

        if expected_val is None and actual_val is None:
            continue

        if expected_val != actual_val:
            error_messages.append(
                f"{member_name}: {type_hints[member_name]} expected {expected_val} but got {actual_val}"
            )

    return error_messages


def assert_class_instance_equality(
    t: type,
    expected: Any,
    actual: Any,
    ignored_properties: Optional[set[str]] = None,
):
    """Given a type t and two instances. Run through the public members of t and assert that the values all match up.
    This will only compare properties whose type passes is_generatable_type.

    Any "private" members beginning with '_' will be skipped

    ignored properties are a set of property names that will NOT be asserted for equality"""
    errors = check_class_instance_equality(t, expected, actual, ignored_properties)
    assert len(errors) == 0, "\n".join(errors)


# ---------------------------------------
#
# The below global values describe the main extension points for adding support for more types to generate
# With a bit of luck - adding more support should be as simple as adding extensions to these lookups
#
# ---------------------------------------

# The set of generators (seed: int) -> typed value (keyed by the type that they generate)
PRIMITIVE_VALUE_GENERATORS: dict[type, Callable[[int], Any]] = {
    int: lambda seed: int(seed),
    str: lambda seed: f"{seed}-str",
    float: lambda seed: float(seed),
    bool: lambda seed: (seed % 2) == 0,
    Decimal: lambda seed: Decimal(seed),
    datetime: lambda seed: datetime(2010, 1, 1, tzinfo=timezone.utc) + timedelta(days=seed) + timedelta(seconds=seed),
}

# the set of all generators (target: type, kwargs: dict[str, Any) -> class instance (keyed by the base type of
# the generated type))
CLASS_INSTANCE_GENERATORS: dict[type, Callable[[type, dict[str, Any]], Any]] = {
    Base: lambda target, kwargs: target(**kwargs),
    BaseXmlModel: lambda target, kwargs: target.model_construct(**kwargs),
    BaseModel: lambda target, kwargs: target.model_construct(**kwargs),
    _PlaceholderDataclassBase: lambda target, kwargs: target(**kwargs),
}

# the set of functions for accessing all members of a class (keyed by the base class for accessing those members)
CLASS_MEMBER_FETCHERS: dict[type, Callable[[type], list[str]]] = {
    Base: lambda target: [name for (name, _) in inspect.getmembers(target)],
    BaseXmlModel: lambda target: list(target.model_fields.keys()),
    BaseModel: lambda target: list(target.model_fields.keys()),
    _PlaceholderDataclassBase: lambda target: [f.name for f in fields(target)],
}

# the set all base class public members keyed by the base class that generated them
BASE_CLASS_PUBLIC_MEMBERS: dict[type, set[str]] = {}
for base_class in CLASS_INSTANCE_GENERATORS.keys():
    members = CLASS_MEMBER_FETCHERS[base_class](base_class)
    BASE_CLASS_PUBLIC_MEMBERS[base_class] = set([m for m in members if is_member_public(m)])
