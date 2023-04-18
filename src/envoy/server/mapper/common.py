
from typing import Union


def generate_mrid(*args: Union[int, float]):
    """Generates an mRID from a set of numbers by concatenating them (hex encoded) - padded to a minimum of 4 digits

    This isn't amazingly robust but for our purposes should allow us to generate a (likely) distinct mrid for
    entities that don't have a corresponding unique ID (eg the entity is entirely virtual with no corresponding
    database model)"""
    return "".join([f"{abs(a):04x}" for a in args])
