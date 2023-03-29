import inspect
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Optional, Union, get_args, get_origin, get_type_hints

from sqlalchemy.orm import Mapped

from envoy.server.model.base import Base


def generate_value(t: type, seed: int = 1, optional_is_none: bool = False) -> Any:
    """Generates a seeded value based on the specified type. Throws an exception if it's not matched

    Feel free to expand this to new types as they come about"""
    if optional_is_none and is_optional_type(t):
        return None

    primitive_type = get_first_generatable_primitive(t, include_optional=False)
    if primitive_type not in PRIMITIVE_VALUE_GENERATORS:
        raise Exception(f"Unsupported type {t} for seed {seed}")

    return PRIMITIVE_VALUE_GENERATORS[primitive_type](seed)


def get_first_generatable_primitive(t: type, include_optional: bool) -> Optional[type]:
    """Given a primitive type - return that type.

    Given a generic type, walk any union arguments looking for a primitive type

    if the type is optional and include_optional is True - the Optional[type] will be returned, otherwise just type will

    Otherwise return None"""

    # if we can generate the type out of the box - we're done
    if t in PRIMITIVE_VALUE_GENERATORS:
        return t

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
    return primitive_type in PRIMITIVE_VALUE_GENERATORS


def is_sql_alchemy_type(t: type) -> bool:
    """Returns True if the specified type is a SQL Alchemy model type"""
    target_type = remove_passthrough_type(t)
    return inspect.isclass(target_type) and Base in target_type.__bases__


def is_optional_type(t: type) -> bool:
    """Returns true if t is an Optional type"""
    if get_origin(t) != Union:
        return False

    return type(None) in get_args(t)


def is_member_public(member_name: str) -> bool:
    """Simple heuristic to test if a member is public (True) or private/internal (False) """
    return len(member_name) > 0 and member_name[0] != '_'


def is_list_type(t: type) -> bool:
    """Returns true if a type looks like a list type"""
    return get_origin(t) == list


def generate_sql_alchemy_instance(t: type,
                                  seed: int = 1,
                                  optional_is_none: bool = False,
                                  generate_relationships: bool = False,
                                  visited_types: Optional[set[type]] = None) -> Any:
    """Given a child class of the SQL Alchemy Base instance - generate an instance of that class
    with all properties being assigned unique (type appropriate) values based off seed

    Any "private" members beginning with '-' will be skipped

    generate_relationships will recursively generate relationships generating instances as required. SQL ALchemy
    will handle assigning backreferences too

    If the type cannot be instantiated due to missing type hints / other info exceptions will be raised"""
    t = remove_passthrough_type(t)

    # stop back references from infinite looping
    if visited_types is None:
        visited_types = set()
    if t in visited_types:
        return None
    visited_types.add(t)

    if not is_sql_alchemy_type(t):
        raise Exception(f"Type {t} does not inherit from {Base} - Known inheritance {t.__bases__}")

    type_hints = get_type_hints(t)

    # We will be creating a dict of property names and their generated values
    # Those values can be basic primitive values or optionally populated
    current_seed = seed
    values: dict[str, Any] = {}
    for (member_name, _) in inspect.getmembers(t):
        if not is_member_public(member_name):
            continue

        if member_name in SQL_ALCHEMY_BASE_PUBLIC_MEMBERS:
            continue

        if member_name not in type_hints:
            raise Exception(f"Type {t} has property {member_name} that is missing a type hint")

        # We generate lists the same as single values (we just wrap the results in a list)
        # keep track of the list state / element type before generating
        member_type = remove_passthrough_type(type_hints[member_name])
        is_list = is_list_type(member_type)
        empty_list: bool = False  # if True - use an empty list
        if is_list:
            member_type = get_args(member_type)[0]

        # if we are passed a string name of a type (such as SQL Alchemy relationships are want to do)
        # eg - list["ChildType"] we need to be able to resolve that
        # Currently we're digging around in the guts of the Base registry - there might be an official way to do this
        # but I haven't yet figured it out.
        if isinstance(member_type, str):
            member_type = Base.registry._class_registry[member_type]

        generated_value: Any = None
        if is_generatable_type(member_type):
            primitive_type = get_first_generatable_primitive(member_type, include_optional=True)
            generated_value = generate_value(primitive_type, seed=current_seed, optional_is_none=optional_is_none)
            current_seed += 1
        elif is_sql_alchemy_type(member_type):
            if generate_relationships:
                generated_value = generate_sql_alchemy_instance(
                    member_type,
                    seed=current_seed,
                    optional_is_none=optional_is_none,
                    generate_relationships=generate_relationships,
                    visited_types=visited_types,
                )
                empty_list = generated_value is None  # This will occur of a backreference visiting an existing type
            else:
                empty_list = True
                generated_value = None
            current_seed += 1000  # Rather than calculating how many seed values were utilised - set it arbitrarily high
        else:
            raise Exception(f"Type {t} has property {member_name} as list {is_list} with type {member_type} that cannot be generated")

        if is_list:
            values[member_name] = [] if empty_list else [generated_value]
        else:
            values[member_name] = generated_value

    return t(**values)


# The set of generators (seed: int) -> typed value keyed by the type that they generate
PRIMITIVE_VALUE_GENERATORS: dict[type, Callable[[int], Any]] = {
    int: lambda seed: int(seed),
    str: lambda seed: f"{seed}-str",
    float: lambda seed: float(seed),
    bool: lambda seed: (seed % 2) == 0,
    Decimal: lambda seed: Decimal(seed),
    datetime: lambda seed: datetime(2010, 1, 1) + timedelta(days=seed) + timedelta(seconds=seed),
}

SQL_ALCHEMY_BASE_PUBLIC_MEMBERS: set[str] = set([m for (m, _) in inspect.getmembers(Base) if is_member_public(m)])