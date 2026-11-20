from sqlalchemy import ColumnElement, and_

from envoy.server.model.site import Site

# The DB stores the NMI split into the 10 character NMI "body" and an (optional) single character checksum
NMI_LENGTH_WITHOUT_CHECKSUM = 10


def split_nmi(nmi: str | None) -> tuple[str | None, str | None]:
    """Splits an externally provided NMI into the (nmi, nmi_checksum) DB representation. NMI's with length <= 10 will
    have a None checksum. Anything longer than 10 chars will have the trailing chars treated as the checksum."""
    if nmi is None or len(nmi) <= NMI_LENGTH_WITHOUT_CHECKSUM:
        return (nmi, None)
    return (nmi[:NMI_LENGTH_WITHOUT_CHECKSUM], nmi[NMI_LENGTH_WITHOUT_CHECKSUM:])


def combine_nmi(nmi: str | None, nmi_checksum: str | None) -> str | None:
    """Combines the (nmi, nmi_checksum) DB representation back into the externally visible NMI"""
    if nmi is None:
        return None
    return nmi + nmi_checksum if nmi_checksum else nmi


def site_nmi_equals(nmi: str) -> ColumnElement[bool]:
    """Generates a where clause that matches Site rows whose (combined) NMI exactly matches nmi"""
    nmi_body, nmi_checksum = split_nmi(nmi)
    if nmi_checksum is None:
        return and_(Site.nmi == nmi_body, Site.nmi_checksum.is_(None))
    return and_(Site.nmi == nmi_body, Site.nmi_checksum == nmi_checksum)
