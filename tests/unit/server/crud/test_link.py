import unittest.mock as mock
from typing import Optional

import pydantic_xml
import pytest
from assertical.fake.generator import generate_class_instance
from envoy_schema.server.schema.sep2.base import BaseXmlModelWithNS
from envoy_schema.server.schema.sep2.identification import Link, ListLink

from envoy.server.crud import link
from envoy.server.crud.link import LinkParameters
from envoy.server.function_set import FunctionSet, FunctionSetStatus
from envoy.server.model.site import Site
from envoy.server.request_scope import BaseRequestScope


@pytest.mark.anyio
@mock.patch.multiple(
    "envoy.server.crud.link",
    check_link_supported=mock.DEFAULT,
    get_formatted_links=mock.DEFAULT,
    get_resource_counts=mock.DEFAULT,
    add_resource_counts_to_links=mock.DEFAULT,
)
async def test_get_supported_links_calls_get_link_field_names_with_model_schema(**kwargs: mock.Mock) -> None:
    model = pydantic_xml.BaseXmlModel

    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)
    with mock.patch("envoy.server.crud.link.get_link_field_names") as get_link_field_names:
        await link.get_supported_links(session=mock.Mock(), model=model, scope=scope, aggregator_id=1, site_id=None)

    get_link_field_names.assert_called_once_with(model)


@pytest.mark.anyio
@mock.patch.multiple(
    "envoy.server.crud.link",
    check_link_supported=mock.DEFAULT,
    get_formatted_links=mock.DEFAULT,
    get_resource_counts=mock.DEFAULT,
    add_resource_counts_to_links=mock.DEFAULT,
)
async def test_get_supported_links_calls_filter_with_check_link_supported_and_link_names(**kwargs: mock.Mock) -> None:
    link_names = ["link1", "link2", "link3"]
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)

    with mock.patch("envoy.server.crud.link.get_link_field_names", return_value=link_names), mock.patch(
        "envoy.server.crud.link.check_link_supported", return_value=True
    ) as check_link_supported, mock.patch("envoy.server.crud.link.filter") as patched_filter:
        await link.get_supported_links(
            session=mock.Mock(), model=mock.Mock(), scope=scope, aggregator_id=123, site_id=None
        )

    patched_filter.assert_called_with(check_link_supported, link_names)


@pytest.mark.anyio
@mock.patch.multiple(
    "envoy.server.crud.link",
    get_link_field_names=mock.DEFAULT,
    check_link_supported=mock.DEFAULT,
    get_resource_counts=mock.DEFAULT,
    add_resource_counts_to_links=mock.DEFAULT,
)
async def test_get_supported_links_calls_get_formatted_links_with_supported_links_names_and_uri_parameters(
    **kwargs: mock.Mock,
) -> None:
    supported_links_names = mock.Mock()
    uri_parameters = mock.Mock()
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)

    with mock.patch("envoy.server.crud.link.filter", return_value=supported_links_names), mock.patch(
        "envoy.server.crud.link.get_formatted_links"
    ) as get_formatted_links:
        await link.get_supported_links(
            session=mock.Mock(),
            model=mock.Mock(),
            scope=scope,
            aggregator_id=1,
            site_id=2,
            uri_parameters=uri_parameters,
        )

    get_formatted_links.assert_called_once_with(
        scope=scope, link_names=supported_links_names, uri_parameters=uri_parameters
    )


@pytest.mark.anyio
@mock.patch.multiple(
    "envoy.server.crud.link",
    get_link_field_names=mock.DEFAULT,
    check_link_supported=mock.DEFAULT,
)
async def test_get_supported_links_calls_add_resource_counts_to_links_with_supported_links_and_resource_counts(
    **kwargs: mock.Mock,
) -> None:
    supported_links = mock.Mock()
    resource_counts = mock.Mock()
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope)
    with mock.patch("envoy.server.crud.link.get_formatted_links", return_value=supported_links), mock.patch(
        "envoy.server.crud.link.get_resource_counts", return_value=resource_counts
    ), mock.patch("envoy.server.crud.link.add_resource_counts_to_links") as add_resource_counts_to_links:
        await link.get_supported_links(
            session=mock.Mock(), model=mock.Mock(), scope=scope, aggregator_id=123, site_id=None
        )

    add_resource_counts_to_links.assert_called_once_with(links=supported_links, resource_counts=resource_counts)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "link_names, site_id, expected_resource_counts",
    [
        (
            ["EndDeviceListLink", "FakeListLink", "JustALink", "AnotherLink"],
            None,
            {"EndDeviceListLink": 4, "FakeListLink": 4},
        ),
        (
            ["EndDeviceListLink"],
            2,
            {"EndDeviceListLink": 4},
        ),
        (  # Check no ListLinks
            ["JustALink", "AnotherLink"],
            None,
            {},
        ),
    ],
)
async def test_get_resource_counts(link_names: list[str], site_id: Optional[int], expected_resource_counts: dict):
    with mock.patch("envoy.server.crud.link.get_resource_count", return_value=4):
        resource_counts = await link.get_resource_counts(
            session=mock.Mock(), link_names=link_names, aggregator_id=1, site_id=site_id
        )
        assert resource_counts == expected_resource_counts


@pytest.mark.anyio
@pytest.mark.parametrize("link_name, resource_count", [("EndDeviceListLink", 5)])
async def test_get_resource_count(link_name: str, resource_count: int):
    with mock.patch("envoy.server.crud.end_device.select_aggregator_site_count", return_value=resource_count):
        assert (
            await link.get_resource_count(session=mock.Mock(), list_link_name=link_name, aggregator_id=1, site_id=None)
            == resource_count
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "link_name, site_resource, expected_count",
    [("EndDeviceListLink", generate_class_instance(Site), 1), ("EndDeviceListLink", None, 0)],
)
async def test_get_resource_count_site_scope(link_name: str, site_resource: Optional[Site], expected_count: int):
    with mock.patch("envoy.server.crud.end_device.select_single_site_with_site_id", return_value=site_resource):
        assert (
            await link.get_resource_count(session=mock.Mock(), list_link_name=link_name, aggregator_id=1, site_id=2)
            == expected_count
        )


@pytest.mark.anyio
@pytest.mark.parametrize("link_name", [("NotASupportedListLink")])
async def test_get_resource_count_raises_exception(link_name: str):
    with pytest.raises(NotImplementedError):
        await link.get_resource_count(session=mock.Mock(), list_link_name=link_name, aggregator_id=1, site_id=None)


@pytest.mark.parametrize(
    "links,resource_counts,updated_links",
    [
        ({}, {}, {}),  # Test empty arguments
        (  # Test with empty link arguments (no href defined for links))
            {
                "CustomerAccountListLink": {},
                "DERProgramListLink": {},
            },
            {"CustomerAccountListLink": 5, "DERProgramListLink": 6},
            {
                "CustomerAccountListLink": {"all_": "5"},
                "DERProgramListLink": {"all_": "6"},
            },
        ),
        (  # Test with counts given as integers
            {
                "CustomerAccountListLink": {"href": "/bill"},
                "DERProgramListLink": {"href": "/derp"},
            },
            {"CustomerAccountListLink": 5, "DERProgramListLink": 6},
            {
                "CustomerAccountListLink": {"href": "/bill", "all_": "5"},
                "DERProgramListLink": {"href": "/derp", "all_": "6"},
            },
        ),
        (  # Test with counts given as strings
            {
                "CustomerAccountListLink": {"href": "/bill"},
                "DERProgramListLink": {"href": "/derp"},
            },
            {"CustomerAccountListLink": "5", "DERProgramListLink": "6"},
            {
                "CustomerAccountListLink": {"href": "/bill", "all_": "5"},
                "DERProgramListLink": {"href": "/derp", "all_": "6"},
            },
        ),
        (  # Test with no resource counts
            {
                "CustomerAccountListLink": {"href": "/bill"},
                "DERProgramListLink": {"href": "/derp"},
            },
            {},
            {
                "CustomerAccountListLink": {"href": "/bill"},
                "DERProgramListLink": {"href": "/derp"},
            },
        ),
    ],
)
def test_add_resource_counts_to_list_links(links: dict, resource_counts: dict, updated_links: dict):
    assert link.add_resource_counts_to_links(links, resource_counts) == updated_links


@pytest.fixture
def link_function_set_mapping():
    return {
        "DeviceCapabilityLink": LinkParameters(uri="", function_set=FunctionSet.DeviceCapability),
        "EndDeviceListLink": LinkParameters(uri="", function_set=FunctionSet.EndDeviceResource),
        "SelfDeviceLink": LinkParameters(uri="", function_set=FunctionSet.SelfDeviceResource),
    }


@pytest.mark.parametrize(
    "function_set_name",
    ["DeviceCapabilityLink", "EndDeviceListLink", "SelfDeviceLink"],
)
@mock.patch("envoy.server.crud.link.check_function_set_supported")
def test_check_link_supported(
    mock_check_function_set_supported: mock.MagicMock,
    link_function_set_mapping: dict,
    function_set_name: str,
):
    # Arrange
    mock_check_function_set_supported.return_value = True

    # Act and Assert
    assert link.check_link_supported(function_set_name, link_map=link_function_set_mapping)


@pytest.mark.parametrize(
    "function_set_name",
    # These function sets names don't exist in the link_function_set_mapping fixture
    ["AccountBalanceLink", "BillingPeriodListLink", "CustomerAccountLink"],
)
@mock.patch("envoy.server.crud.link.check_function_set_supported")
def test_check_link_supported_raises_exception(
    mock_check_function_set_supported: mock.MagicMock,
    link_function_set_mapping: dict,
    function_set_name: str,
):
    # Arrange
    mock_check_function_set_supported.return_value = True

    # Act and Assert
    with pytest.raises(ValueError):
        link.check_link_supported(function_set_name, link_map=link_function_set_mapping)


@pytest.fixture
def function_set_status_mapping():
    # This is a stripped down subset of the full mapping found in envoy/server/schema/function_set.py
    return {
        FunctionSet.DeviceCapability: FunctionSetStatus.SUPPORTED,
        FunctionSet.SelfDeviceResource: FunctionSetStatus.UNSUPPORTED,
        FunctionSet.EndDeviceResource: FunctionSetStatus.PARTIAL_SUPPORT,
    }


@pytest.mark.parametrize(
    "function_set, function_set_status",
    [
        (FunctionSet.DeviceCapability, True),
        (FunctionSet.SelfDeviceResource, False),
        (FunctionSet.EndDeviceResource, False),
    ],
)
def test_check_function_set_supported(
    function_set_status_mapping: dict, function_set: FunctionSet, function_set_status: FunctionSetStatus
):
    assert (
        link.check_function_set_supported(function_set, function_set_status=function_set_status_mapping)
        == function_set_status
    )


@pytest.mark.parametrize(
    "function_set",
    # These function sets don't exist in the function_set_status_mapping fixture
    [FunctionSet.Billing, FunctionSet.ConfigurationResource],
)
def test_check_function_set_supported_raise_exception(function_set_status_mapping: dict, function_set: FunctionSet):
    with pytest.raises(ValueError):
        link.check_function_set_supported(function_set, function_set_status=function_set_status_mapping)


@pytest.mark.parametrize(
    "link_names, uri_parameters, expected",
    [
        (  # Test a link that requires a single uri parameter
            ["EndDeviceLink"],
            {"site_id": 5},
            {"EndDeviceLink": {"href": "/edev/5"}},
        ),
        (  # Test a bunch of links that don't require uri parameters
            [
                "CustomerAccountListLink",
                # "DERProgramListLink",
                "DemandResponseProgramListLink",
                "EndDeviceListLink",
                "FileListLink",
                "MessagingProgramListLink",
                "MirrorUsagePointListLink",
                "PrepaymentListLink",
                "ResponseSetListLink",
                "SelfDeviceLink",
                # "TariffProfileListLink",
                "TimeLink",
                "UsagePointListLink",
            ],
            {},
            {
                "CustomerAccountListLink": {"href": "/bill"},
                # DERProgramListLink is now site scoped
                # "DERProgramListLink": {"href": "/derp"},
                "DemandResponseProgramListLink": {"href": "/dr"},
                "EndDeviceListLink": {"href": "/edev"},
                "FileListLink": {"href": "/file"},
                "MessagingProgramListLink": {"href": "/msg"},
                "MirrorUsagePointListLink": {"href": "/mup"},
                "PrepaymentListLink": {"href": "/ppy"},
                "ResponseSetListLink": {"href": "/rsps"},
                "SelfDeviceLink": {"href": "/sdev"},
                # TariffProfileListLink is now site scoped
                # "TariffProfileListLink": {"href": "/tp"},
                "TimeLink": {"href": "/tm"},
                "UsagePointListLink": {"href": "/upt"},
            },
        ),
    ],
)
def test_get_formatted_links(link_names, uri_parameters, expected):
    scope: BaseRequestScope = generate_class_instance(BaseRequestScope, href_prefix=None)
    assert link.get_formatted_links(link_names, scope, uri_parameters) == expected


@pytest.mark.parametrize(
    "link_names, uri_parameters",
    [
        (  # Test a link that requires a single uri parameter that is missing
            ["CustomerAccountLink"],
            {},
        ),
        (  # Test a link that requires a single uri parameter that is missing (another supplied)
            ["CustomerAccountLink"],
            {"site_id": 5},
        ),
    ],
)
def test_get_formatted_links_raises_exception(link_names, uri_parameters):
    with pytest.raises(link.MissingUriParameterError):
        link.get_formatted_links(link_names, generate_class_instance(BaseRequestScope), uri_parameters)


class NoProps(BaseXmlModelWithNS):
    pass


class NoListLinkOrLinkPrimitives(BaseXmlModelWithNS):
    title: str = pydantic_xml.element()
    count: int = pydantic_xml.element()


class NoListLinkOrLinkComplex(BaseXmlModelWithNS):
    names: list[str] = pydantic_xml.element()
    title: Optional[list[str]] = pydantic_xml.element()
    obj: NoListLinkOrLinkPrimitives = pydantic_xml.element()


class WithLinks(BaseXmlModelWithNS):
    names: list[str] = pydantic_xml.element()
    title: Optional[list[str]] = pydantic_xml.element()
    obj: NoListLinkOrLinkPrimitives = pydantic_xml.element()
    mandatory_list: ListLink = pydantic_xml.element()
    optional_list: Optional[ListLink] = pydantic_xml.element()
    mandatory_link: Link = pydantic_xml.element()
    optional_link: Optional[Link] = pydantic_xml.element()


@pytest.mark.parametrize(
    "model, expected",
    [
        (NoProps, []),
        (NoListLinkOrLinkPrimitives, []),
        (NoListLinkOrLinkComplex, []),
        (
            WithLinks,
            [
                "mandatory_list",
                "optional_list",
                "mandatory_link",
                "optional_link",
            ],
        ),
    ],
)
def test_get_link_field_names(model: type, expected: list[str]):
    assert link.get_link_field_names(model) == expected
