""" Module for CSIP-AUS specific middleware and depends.
"""

from fastapi import Request


class ReplaceIncomingXmlNsDepends:
    """This depends modifies XML namespaces in the incoming request payload as defined in the 'replace_ns_map'.

    Specific usecase: The latest CSIP-AUS standard (v1.1a) introduces a variation to the XML namespace. The original
    namespace http://csipaus.org/ns is now https://csipaus.org/ns. This depends checks for the legacy namespace in
    the request payload and modifies it to the updated namespace. Note that current thinking is for this is to be a
    temporary approach in support of migration to the new namespace.
    """

    def __init__(self, replace_ns_map: dict):
        """
        Args:
            replace_ns_map (dict): dictionary with key being original namespace and value the new namespace.
        """
        self.replace_ns_map: dict[str, str] = replace_ns_map

    async def __call__(self, request: Request) -> None:
        body = await request.body()

        for oldns, newns in self.replace_ns_map.items():
            # replace oldns with newns, where count=1 i.e. we assume that namespace will only be defined once in the
            # entire XML tree. NB. If duplicate exists, this will not be replaced and raise a validation exception.
            body = body.replace(oldns.encode("utf-8"), newns.encode("utf-8"), 1)

        request._body = body
