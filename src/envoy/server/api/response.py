from fastapi import Response
from pydantic_xml import BaseXmlModel

SEP_XML_MIME: str = "application/sep+xml"


class XmlResponse(Response):
    media_type = SEP_XML_MIME

    def render(self, content: BaseXmlModel) -> bytes:
        return content.to_xml(skip_empty=True)
