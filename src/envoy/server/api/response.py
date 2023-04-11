from typing import Generic, Type, TypeVar

from fastapi import HTTPException, Request, Response
from pydantic_xml import BaseXmlModel

SEP_XML_MIME: str = "application/sep+xml"

LOCATION_HEADER_NAME: str = "Location"


class XmlResponse(Response):
    media_type = SEP_XML_MIME

    def render(self, content: BaseXmlModel) -> bytes:
        return content.to_xml(skip_empty=True)


TBaseXmlModel = TypeVar("TBaseXmlModel", bound=BaseXmlModel)


class XmlRequest(Generic[TBaseXmlModel]):
    def __init__(self, model_class: Type[TBaseXmlModel]):
        self.model_class = model_class

    async def __call__(self, request: Request) -> TBaseXmlModel:
        try:
            return self.model_class.from_xml(await request.body())

        except (ValueError, TypeError) as err:
            raise HTTPException(detail=f"{err}", status_code=422)
