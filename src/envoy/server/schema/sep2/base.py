from pydantic_xml import BaseXmlModel
from pydantic_xml.element import SearchMode

nsmap = {"": "urn:ieee:std:2030.5:ns", "csipaus": "http://csipaus.org/ns"}


class BaseXmlModelWithNS(BaseXmlModel):
    def __init_subclass__(
        cls,
        *args,
        **kwargs,
    ):
        super().__init_subclass__(*args, **kwargs)
        cls.__xml_nsmap__ = nsmap
        cls.__xml_search_mode__ = SearchMode.UNORDERED
