from fastapi import Response

from pydantic_xml import BaseXmlModel


class XmlResponse(Response):
    media_type = "application/sep+xml"

    def render(self, content: BaseXmlModel) -> bytes:
        return content.to_xml(skip_empty=True)
