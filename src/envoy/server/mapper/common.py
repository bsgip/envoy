from itertools import chain
from typing import Any, Union

from envoy.server.api.request import RequestStateParameters


def generate_mrid(*args: Union[int, float]):
    """Generates an mRID from a set of numbers by concatenating them (hex encoded) - padded to a minimum of 4 digits

    This isn't amazingly robust but for our purposes should allow us to generate a (likely) distinct mrid for
    entities that don't have a corresponding unique ID (eg the entity is entirely virtual with no corresponding
    database model)"""
    return "".join([f"{abs(a):04x}" for a in args])


def generate_href(uri_format: str, request_state_params: RequestStateParameters, *args: Any, **kwargs: Any):
    """Generates a href from a format string and an optional static prefix. Any args/kwargs will be forwarded to
    str.format (being applied to uri_format).

    If a prefix is applied - the state of the leading slash will mirror uri_format"""
    uri = uri_format.format(*args, **kwargs)
    prefix = request_state_params.href_prefix
    if prefix is None:
        return uri

    # The uri_format dictates whether the uri should be relative/absolute
    join_parts = (p for p in chain(prefix.split("/"), uri.split("/")) if p)
    joined = "/".join(join_parts)
    if uri_format.startswith("/"):
        if joined.startswith("/"):
            return joined
        else:
            return "/" + joined
    else:
        if joined.startswith("/"):
            return joined[1:]
        else:
            return joined
