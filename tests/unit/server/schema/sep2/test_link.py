import pytest

from envoy.server.schema.sep2 import link


@pytest.mark.parametrize(
    "link_names, uri_params, expected",
    [
        (
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
        )
    ],
)
def test_get_formatted_links(link_names, uri_params, expected):
    assert link.get_formatted_links(link_names, uri_params) == expected


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
