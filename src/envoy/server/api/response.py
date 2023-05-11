from http import HTTPStatus
from typing import Generic, Type, TypeVar, Union

from fastapi import HTTPException, Request, Response
from pydantic_xml import BaseXmlModel

SEP_XML_MIME: str = "application/sep+xml"

LOCATION_HEADER_NAME: str = "Location"


class XmlResponse(Response):
    media_type = SEP_XML_MIME

    def render(self, content: BaseXmlModel) -> Union[str, bytes]:  # type: ignore [override] # Base is too restrictive
        return content.to_xml(skip_empty=True)


TBaseXmlModel = TypeVar("TBaseXmlModel", bound=BaseXmlModel)


class XmlRequest(Generic[TBaseXmlModel]):
    def __init__(self, model_class: Type[TBaseXmlModel]):
        self.model_class = model_class

    async def __call__(self, request: Request) -> TBaseXmlModel:
        try:
            model = self.model_class.from_xml(await request.body())
        except (ValueError, TypeError) as err:
            raise HTTPException(detail=f"{err}", status_code=422)

        if not model:
            raise HTTPException(HTTPStatus.BAD_REQUEST.value, detail="request body couldn't map to model XML")
        return model  # type: ignore [return-value] # The pydantic XML return type hint isn't quite correct
