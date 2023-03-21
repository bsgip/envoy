from typing import Generic, Type, TypeVar

from fastapi import HTTPException, Request, Response
from pydantic_xml import BaseXmlModel


class XmlResponse(Response):
    media_type = "application/sep+xml"

    def render(self, content: BaseXmlModel) -> bytes:
        return content.to_xml(skip_empty=True)


T = TypeVar("T", bound=BaseXmlModel)


class XmlRequest(Generic[T]):
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class

    async def __call__(self, request: Request) -> T:
        try:
            return self.model_class.from_xml(await request.body())

        except (ValueError, TypeError) as err:
            raise HTTPException(detail=f"{err}", status_code=422)
