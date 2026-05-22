from datetime import datetime


def build_paging_params(
    start: int | None = None, limit: int | None = None, changed_after: datetime | None = None
) -> str:
    """Builds up a sep2 paging query string in the form of ?s={start}&l={limit}&a={changed_after}.
    None params will not be included in the query string"""

    parts: list[str] = []
    if start is not None:
        parts.append(f"s={start}")
    if limit is not None:
        parts.append(f"l={limit}")
    if changed_after is not None:
        parts.append(f"a={int(changed_after.timestamp())}")

    return "?" + "&".join(parts)
