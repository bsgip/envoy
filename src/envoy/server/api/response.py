from http import HTTPStatus
from typing import Generic, Type, TypeVar, Union

from fastapi import HTTPException, Request, Response
from pydantic_xml import BaseXmlModel
from pydantic_xml.errors import ParsingError

SEP_XML_MIME: str = "application/sep+xml"

LOCATION_HEADER_NAME: str = "Location"

TBaseXmlModel = TypeVar("TBaseXmlModel", bound=BaseXmlModel)


class XmlResponse(Response):
    media_type = SEP_XML_MIME

    def render(self, content: BaseXmlModel) -> Union[str, bytes]:  # type: ignore [override] # Base is too restrictive
        return content.to_xml(skip_empty=False, exclude_none=True, exclude_unset=True)


class XmlRequest(Generic[TBaseXmlModel]):
    """
    Create an XmlRequest object which is used by FastApi to parse the XML body of POST/PUT requests
    into a model object (in this context models refers the Sep2 schema (model) object and not
    the database models objects).

    The standard usage is to have only one request representation. Here is an example taken
    from the End Device function set, where EndDeviceRequest is the request representation.

    payload: Annotated[EndDeviceRequest, Depends(XmlRequest(EndDeviceRequest))]

    XmlRequest does support multiple request representations. In these case, a list of possible request representations
    are passed to XmlRequest. XmlRequest will then try to parse the XML in turn for each request representation,
    returning as soon as parsing succeeds. Since we return on the first successful parsing, the order of the model
    classes is significant when the same XML request body could be successfully parsed by more than one model classes.

    Here is an example of using multiple request representations from the Metering Mirror function set. It accepts
    either a MirrorMeterReadingRequest or a MirrorMeterReadingListRequest.

    payload: Annotated[
        Union[MirrorMeterReadingRequest, MirrorMeterReadingListRequest],
        Depends(XmlRequest(MirrorMeterReadingRequest, MirrorMeterReadingListRequest)),
    ]

    If passing fails for all the request representations, then a HTTP Bad Request is raised.
    """

    def __init__(self, *model_classes: Type[TBaseXmlModel]):
        self.model_classes = model_classes

    async def __call__(self, request: Request) -> TBaseXmlModel:
        model = None
        for model_class in self.model_classes:
            try:
                body = await request.body()
                model = model_class.from_xml(body)
                break  # Stop at the first model class that successfully parses
            except ParsingError:
                pass

        # A ParsingError was raised for all the model classes, so parsing the body failed
        if not model:
            raise HTTPException(HTTPStatus.BAD_REQUEST.value, detail="request body couldn't map to model XML")

        return model  # type: ignore [return-value] # The pydantic XML return type hint isn't quite correct
