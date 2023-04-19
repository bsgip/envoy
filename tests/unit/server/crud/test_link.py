import unittest.mock as mock

import pytest

from envoy.server.crud import link
from envoy.server.schema.function_set import FunctionSet, FunctionSetStatus


@pytest.mark.anyio
@pytest.mark.parametrize("link_name, resource_count", [("EndDeviceListLink", 5)])
@mock.patch("fastapi_async_sqlalchemy.middleware.DBSessionMeta.session")
async def test_get_resource_count(_: mock.Mock, link_name: str, resource_count: int):
    with mock.patch("envoy.server.crud.end_device.select_aggregator_site_count", return_value=resource_count):
        assert await link.get_resource_count(link_name, aggregator_id=1) == resource_count


@pytest.mark.anyio
@pytest.mark.parametrize("link_name", [("NotASupportedListLink")])
async def test_get_resource_count_raises_exception(link_name: str):
    with pytest.raises(NotImplementedError):
        await link.get_resource_count(link_name, aggregator_id=1)


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
        "DeviceCapabilityLink": {
            "function-set": FunctionSet.DeviceCapability,
        },
        "EndDeviceListLink": {
            "function-set": FunctionSet.EndDeviceResource,
        },
        "SelfDeviceLink": {
            "function-set": FunctionSet.SelfDeviceResource,
        },
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
                "DERProgramListLink",
                "DemandResponseProgramListLink",
                "EndDeviceListLink",
                "FileListLink",
                "MessagingProgramListLink",
                "MirrorUsagePointListLink",
                "PrepaymentListLink",
                "ResponseSetListLink",
                "SelfDeviceLink",
                "TariffProfileListLink",
                "TimeLink",
                "UsagePointListLink",
            ],
            {},
            {
                "CustomerAccountListLink": {"href": "/bill"},
                "DERProgramListLink": {"href": "/derp"},
                "DemandResponseProgramListLink": {"href": "/dr"},
                "EndDeviceListLink": {"href": "/edev"},
                "FileListLink": {"href": "/file"},
                "MessagingProgramListLink": {"href": "/msg"},
                "MirrorUsagePointListLink": {"href": "/mup"},
                "PrepaymentListLink": {"href": "/ppy"},
                "ResponseSetListLink": {"href": "/rsps"},
                "SelfDeviceLink": {"href": "/sdev"},
                "TariffProfileListLink": {"href": "/tp"},
                "TimeLink": {"href": "/tm"},
                "UsagePointListLink": {"href": "/upt"},
            },
        ),
    ],
)
def test_get_formatted_links(link_names, uri_parameters, expected):
    assert link.get_formatted_links(link_names, uri_parameters) == expected


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
        link.get_formatted_links(link_names, uri_parameters)


@pytest.mark.parametrize(
    "schema, expected",
    [
        ({"properties": {}}, []),  # No properties
        (
            {"properties": {"href": {"title": "Href", "enum": ["/fakeuri"], "type": "string"}}},
            [],
        ),  # No ListLink or Link fields
        ({"properties": {"MyList": {"$ref": "#/definitions/List"}}}, []),  # field with $ref not a ListLink or Link
        (
            {
                "properties": {
                    "href": {"title": "Href", "enum": ["/fakeuri"], "type": "string"},
                    "pollRate": {"title": "Pollrate", "type": "integer"},
                    "SelfDeviceLink": {"$ref": "#/definitions/Link"},
                    "EndDeviceListLink": {"$ref": "#/definitions/ListLink"},
                    "MirrorUsagePointListLink": {"$ref": "#/definitions/ListLink"},
                }
            },
            [
                "SelfDeviceLink",
                "EndDeviceListLink",
                "MirrorUsagePointListLink",
            ],
        ),
        (
            {
                "properties": {
                    "href": {"title": "Href", "default": "/fakeuri", "type": "string"},
                    "TimeLink": {"$ref": "#/definitions/Link"},
                    "CustomerAccountListLink": {"$ref": "#/definitions/ListLink"},
                    "DemandResponseProgramListLink": {"$ref": "#/definitions/ListLink"},
                    "DERProgramListLink": {"$ref": "#/definitions/ListLink"},
                    "FileListLink": {"$ref": "#/definitions/ListLink"},
                    "MessagingProgramListLink": {"$ref": "#/definitions/ListLink"},
                    "PrepaymentListLink": {"$ref": "#/definitions/ListLink"},
                    "ResponseSetListLink": {"$ref": "#/definitions/ListLink"},
                    "TariffProfileListLink": {"$ref": "#/definitions/ListLink"},
                    "UsagePointListLink": {"$ref": "#/definitions/ListLink"},
                    "pollRate": {"title": "Pollrate", "type": "integer"},
                    "SelfDeviceLink": {"$ref": "#/definitions/Link"},
                    "EndDeviceListLink": {"$ref": "#/definitions/ListLink"},
                    "MirrorUsagePointListLink": {"$ref": "#/definitions/ListLink"},
                }
            },
            [
                "TimeLink",
                "CustomerAccountListLink",
                "DemandResponseProgramListLink",
                "DERProgramListLink",
                "FileListLink",
                "MessagingProgramListLink",
                "PrepaymentListLink",
                "ResponseSetListLink",
                "TariffProfileListLink",
                "UsagePointListLink",
                "SelfDeviceLink",
                "EndDeviceListLink",
                "MirrorUsagePointListLink",
            ],
        ),
    ],
)
def test_get_link_field_names(schema: dict, expected: list[str]):
    assert link.get_link_field_names(schema) == expected
