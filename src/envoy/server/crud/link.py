import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

import pydantic_xml
from envoy_schema.server.schema import uri
from envoy_schema.server.schema.function_set import FUNCTION_SET_STATUS, FunctionSet, FunctionSetStatus
from sqlalchemy.ext.asyncio import AsyncSession

from envoy.server.api.request import RequestStateParameters
from envoy.server.crud import end_device, site_reading
from envoy.server.mapper.common import generate_href

logger = logging.getLogger(__name__)


class MissingUriParameterError(Exception):
    pass


@dataclass
class LinkParameters:
    uri: str
    function_set: FunctionSet


SEP2_LINK_MAP = {
    "AccountBalanceLink": LinkParameters(uri=uri.AccountBalanceUri, function_set=FunctionSet.Prepayment),
    "ActiveBillingPeriodListLink": LinkParameters(uri=uri.ActiveBillingPeriodListUri, function_set=FunctionSet.Billing),
    "ActiveCreditRegisterListLink": LinkParameters(
        uri=uri.ActiveCreditRegisterListUri, function_set=FunctionSet.Unknown
    ),  # There is NO ActiveCreditRegisterList in Sep2!
    "ActiveDERControlListLink": LinkParameters(
        uri=uri.ActiveDERControlListUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "ActiveEndDeviceControlListLink": LinkParameters(
        uri=uri.ActiveEndDeviceControlListUri, function_set=FunctionSet.DemandResponseAndLoadControl
    ),
    "ActiveFlowReservationListLink": LinkParameters(
        uri=uri.ActiveFlowReservationListUri, function_set=FunctionSet.Unknown
    ),  # There is NO ActiveFlowReservationList in Sep2!
    "ActiveProjectionReadingListLink": LinkParameters(
        uri=uri.ActiveProjectionReadingListUri, function_set=FunctionSet.Unknown
    ),  # There is NO ActiveProjectionReadingList in Sep2!
    "ActiveSupplyInterruptionOverrideListLink": LinkParameters(
        uri=uri.ActiveSupplyInterruptionOverrideListUri, function_set=FunctionSet.Prepayment
    ),
    "ActiveTargetReadingListLink": LinkParameters(
        uri=uri.ActiveTargetReadingListUri, function_set=FunctionSet.Unknown
    ),  # There is NO ActiveTargeReadingList in Sep2!
    "ActiveTextMessageListLink": LinkParameters(uri=uri.ActiveTextMessageListUri, function_set=FunctionSet.Messaging),
    "ActiveTimeTariffIntervalListLink": LinkParameters(
        uri=uri.ActiveTimeTariffIntervalListUri, function_set=FunctionSet.Pricing
    ),
    "AssociatedDERProgramListLink": LinkParameters(
        uri=uri.AssociatedDERProgramListUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "AssociatedUsagePointLink": LinkParameters(
        uri=uri.AssociatedUsagePointUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "BillingPeriodListLink": LinkParameters(uri=uri.BillingPeriodListUri, function_set=FunctionSet.Billing),
    "BillingReadingListLink": LinkParameters(uri=uri.BillingReadingListUri, function_set=FunctionSet.Billing),
    "BillingReadingSetListLink": LinkParameters(uri=uri.BillingReadingSetListUri, function_set=FunctionSet.Billing),
    "ConfigurationLink": LinkParameters(uri=uri.ConfigurationUri, function_set=FunctionSet.ConfigurationResource),
    "ConsumptionTariffIntervalListLink": LinkParameters(
        uri=uri.ConsumptionTariffIntervalListUri, function_set=FunctionSet.Pricing
    ),
    "CreditRegisterListLink": LinkParameters(uri=uri.CreditRegisterListUri, function_set=FunctionSet.Prepayment),
    "CustomerAccountListLink": LinkParameters(uri=uri.CustomerAccountListUri, function_set=FunctionSet.Billing),
    "CustomerAccountLink": LinkParameters(uri=uri.CustomerAccountUri, function_set=FunctionSet.Billing),
    "CustomerAgreementListLink": LinkParameters(uri=uri.CustomerAgreementListUri, function_set=FunctionSet.Billing),
    "DefaultDERControlLink": LinkParameters(
        uri=uri.DefaultDERControlUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "DemandResponseProgramListLink": LinkParameters(
        uri=uri.DemandResponseProgramListUri, function_set=FunctionSet.DemandResponseAndLoadControl
    ),
    "DemandResponseProgramLink": LinkParameters(
        uri=uri.DemandResponseProgramUri, function_set=FunctionSet.DemandResponseAndLoadControl
    ),
    "DERAvailabilityLink": LinkParameters(
        uri=uri.DERAvailabilityUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "DERCapabilityLink": LinkParameters(uri=uri.DERCapabilityUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERControlListLink": LinkParameters(
        uri=uri.DERControlListUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "DERCurveListLink": LinkParameters(uri=uri.DERCurveListUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERCurveLink": LinkParameters(uri=uri.DERCurveUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERListLink": LinkParameters(uri=uri.DERListUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERProgramListLink": LinkParameters(
        uri=uri.DERProgramListUri, function_set=FunctionSet.DistributedEnergyResources
    ),
    "DERProgramLink": LinkParameters(uri=uri.DERProgramUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERSettingsLink": LinkParameters(uri=uri.DERSettingsUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERStatusLink": LinkParameters(uri=uri.DERStatusUri, function_set=FunctionSet.DistributedEnergyResources),
    "DERLink": LinkParameters(uri=uri.DERUri, function_set=FunctionSet.DistributedEnergyResources),
    "DeviceCapabilityLink": LinkParameters(uri=uri.DeviceCapabilityUri, function_set=FunctionSet.DeviceCapability),
    "DeviceInformationLink": LinkParameters(uri=uri.DeviceInformationUri, function_set=FunctionSet.DeviceInformation),
    "DeviceStatusLink": LinkParameters(uri=uri.DeviceStatusUri, function_set=FunctionSet.EndDeviceResource),
    "EndDeviceControlListLink": LinkParameters(
        uri=uri.EndDeviceControlListUri, function_set=FunctionSet.DemandResponseAndLoadControl
    ),
    "EndDeviceListLink": LinkParameters(uri=uri.EndDeviceListUri, function_set=FunctionSet.EndDeviceResource),
    "EndDeviceLink": LinkParameters(uri=uri.EndDeviceUri, function_set=FunctionSet.EndDeviceResource),
    "FileListLink": LinkParameters(uri=uri.FileListUri, function_set=FunctionSet.SoftwareDownload),
    "FileStatusLink": LinkParameters(uri=uri.FileStatusUri, function_set=FunctionSet.SoftwareDownload),
    "FileLink": LinkParameters(uri=uri.FileUri, function_set=FunctionSet.SoftwareDownload),
    "FlowReservationRequestListLink": LinkParameters(
        uri=uri.FlowReservationRequestListUri, function_set=FunctionSet.FlowReservation
    ),
    "FlowReservationResponseListLink": LinkParameters(
        uri=uri.FlowReservationResponseListUri, function_set=FunctionSet.FlowReservation
    ),
    "FunctionSetAssignmentsListLink": LinkParameters(
        uri=uri.FunctionSetAssignmentsListUri, function_set=FunctionSet.FunctionSetAssignments
    ),
    "HistoricalReadingListLink": LinkParameters(uri=uri.HistoricalReadingListUri, function_set=FunctionSet.Billing),
    "IPAddrListLink": LinkParameters(uri=uri.IPAddrListUri, function_set=FunctionSet.NetworkStatus),
    "IPInterfaceListLink": LinkParameters(uri=uri.IPInterfaceListUri, function_set=FunctionSet.NetworkStatus),
    "LLInterfaceListLink": LinkParameters(uri=uri.LLInterfaceListUri, function_set=FunctionSet.NetworkStatus),
    "LoadShedAvailabilityListLink": LinkParameters(
        uri=uri.LoadShedAvailabilityListUri, function_set=FunctionSet.DemandResponseAndLoadControl
    ),
    "LogEventListLink": LinkParameters(uri=uri.LogEventListUri, function_set=FunctionSet.LogEvent),
    "MessagingProgramListLink": LinkParameters(uri=uri.MessagingProgramListUri, function_set=FunctionSet.Messaging),
    "MeterReadingListLink": LinkParameters(uri=uri.MeterReadingListUri, function_set=FunctionSet.Metering),
    "MeterReadingLink": LinkParameters(uri=uri.MeterReadingUri, function_set=FunctionSet.Metering),
    "MirrorUsagePointListLink": LinkParameters(
        uri=uri.MirrorUsagePointListUri, function_set=FunctionSet.MeteringMirror
    ),
    "NeighborListLink": LinkParameters(uri=uri.NeighborListUri, function_set=FunctionSet.NetworkStatus),
    "NotificationListLink": LinkParameters(
        uri=uri.NotificationListUri, function_set=FunctionSet.SubscriptionAndNotification
    ),
    "PowerStatusLink": LinkParameters(uri=uri.PowerStatusUri, function_set=FunctionSet.PowerStatus),
    "PrepaymentListLink": LinkParameters(uri=uri.PrepaymentListUri, function_set=FunctionSet.Prepayment),
    "PrepaymentLink": LinkParameters(uri=uri.PrepaymentUri, function_set=FunctionSet.Prepayment),
    "PrepayOperationStatusLink": LinkParameters(uri=uri.PrepayOperationStatusUri, function_set=FunctionSet.Prepayment),
    "PriceResponseCfgListLink": LinkParameters(
        uri=uri.PriceResponseCfgListUri, function_set=FunctionSet.ConfigurationResource
    ),
    "ProjectionReadingListLink": LinkParameters(uri=uri.ProjectionReadingListUri, function_set=FunctionSet.Billing),
    "RateComponentListLink": LinkParameters(uri=uri.RateComponentListUri, function_set=FunctionSet.Pricing),
    "RateComponentLink": LinkParameters(uri=uri.RateComponentUri, function_set=FunctionSet.Pricing),
    "ReadingListLink": LinkParameters(uri=uri.ReadingListUri, function_set=FunctionSet.Metering),
    "ReadingSetListLink": LinkParameters(uri=uri.ReadingSetListUri, function_set=FunctionSet.Metering),
    "ReadingTypeLink": LinkParameters(uri=uri.ReadingTypeUri, function_set=FunctionSet.Metering),
    "ReadingLink": LinkParameters(uri=uri.ReadingUri, function_set=FunctionSet.Metering),
    "RegistrationLink": LinkParameters(uri=uri.RegistrationUri, function_set=FunctionSet.EndDeviceResource),
    "ResponseListLink": LinkParameters(uri=uri.ResponseListUri, function_set=FunctionSet.Response),
    "ResponseSetListLink": LinkParameters(uri=uri.ResponseSetListUri, function_set=FunctionSet.Response),
    "RPLInstanceListLink": LinkParameters(uri=uri.RPLInstanceListUri, function_set=FunctionSet.NetworkStatus),
    "RPLSourceRoutesListLink": LinkParameters(uri=uri.RPLSourceRoutesListUri, function_set=FunctionSet.NetworkStatus),
    "SelfDeviceLink": LinkParameters(uri=uri.SelfDeviceUri, function_set=FunctionSet.SelfDeviceResource),
    "ServiceSupplierLink": LinkParameters(uri=uri.ServiceSupplierUri, function_set=FunctionSet.Billing),
    "SubscriptionListLink": LinkParameters(
        uri=uri.SubscriptionListUri, function_set=FunctionSet.SubscriptionAndNotification
    ),
    "SupplyInterruptionOverrideListLink": LinkParameters(
        uri=uri.SupplyInterruptionOverrideListUri, function_set=FunctionSet.Prepayment
    ),
    "SupportedLocaleListLink": LinkParameters(
        uri=uri.SupportedLocaleListUri, function_set=FunctionSet.DeviceInformation
    ),
    "TargetReadingListLink": LinkParameters(uri=uri.TargetReadingListUri, function_set=FunctionSet.Billing),
    "TariffProfileListLink": LinkParameters(uri=uri.TariffProfileListUnscopedUri, function_set=FunctionSet.Pricing),
    "TariffProfileLink": LinkParameters(uri=uri.TariffProfileUri, function_set=FunctionSet.Pricing),
    "TextMessageListLink": LinkParameters(uri=uri.TextMessageListUri, function_set=FunctionSet.Messaging),
    "TimeTariffIntervalListLink": LinkParameters(uri=uri.TimeTariffIntervalListUri, function_set=FunctionSet.Pricing),
    "TimeLink": LinkParameters(uri=uri.TimeUri, function_set=FunctionSet.Time),
    "UsagePointListLink": LinkParameters(uri=uri.UsagePointListUri, function_set=FunctionSet.Metering),
    "UsagePointLink": LinkParameters(uri=uri.UsagePointUri, function_set=FunctionSet.Metering),
}


async def get_supported_links(
    session: AsyncSession,
    model: type[pydantic_xml.BaseXmlModel],
    rs_params: RequestStateParameters,
    uri_parameters: Optional[dict] = None,
) -> dict[str, dict[str, str]]:
    """
    Generates all support links for a given model.

    A link is supported if the function set it belongs has been implemented.

    The following steps are performed:
    - Finds all the Links and ListLink in the model
    - Discards any that belong to unsupported function sets
    - Inserts the uri_parameters in the link's URI
    - If the Link is a ListLink: also determines the resource counts ("all_" key)
    - Returns a mapping from the link name to the URI and resource counts e.g.

    {
        "EndDeviceListLink": {
            "href": "/edev",
            "all_": 10,
        }
    }

    Args:
        model: A pydantic model e.g. DeviceCapabilityResponse
        aggregator_id: The aggregator id
        uri_parameters: A dictionary containing parameters to be inserted into the URIs e.g. {"site_id": 5}

    Returns:
        Mapping from Link Name to the formatted URI and if Link is a ListLink the resource counts.

    """
    link_names = get_link_field_names(schema=model.schema())
    supported_links_names = filter(check_link_supported, link_names)
    supported_links = get_formatted_links(
        rs_params=rs_params, link_names=supported_links_names, uri_parameters=uri_parameters
    )
    resource_counts = await get_resource_counts(
        session=session, link_names=supported_links.keys(), aggregator_id=rs_params.aggregator_id
    )
    updated_supported_links = add_resource_counts_to_links(links=supported_links, resource_counts=resource_counts)

    return updated_supported_links


async def get_resource_counts(session: AsyncSession, link_names: Iterable[str], aggregator_id: int) -> dict[str, int]:
    """
    Returns the resource counts for all the ListLinks in list.

    Calls 'get_resource_count' for each ListLink.

    Args:
        link_names: A list of Links. This can be a mixture of both Links and ListLinks.
        aggregator_id: The id of the aggregator (determines which resources are accessible)

    Returns:
        A mapping for each ListList to it's resource count.
    """
    resource_counts = {}
    for link_name in link_names:
        if link_name.endswith("ListLink"):
            try:
                count = await get_resource_count(session=session, list_link_name=link_name, aggregator_id=aggregator_id)
                resource_counts[link_name] = count
            except NotImplementedError as e:
                logger.debug(e)
    return resource_counts


async def get_resource_count(session: AsyncSession, list_link_name: str, aggregator_id: int) -> int:
    """
    Returns the resource count for given ListLink.

    For example, for EndDeviceListLink the resource count is the number
    of end devices associated with the aggregator.

    Args:
        list_link_name: The name of the ListLink e.g. "EndDeviceListLink"
        aggregator_id: The id of the aggregator (determines which resources are accessible)

    Returns:
        The resource count.

    Raises:
        NotImplementedError: Raised when a ListLink doesn't have a resource count lookup method.
    """
    if list_link_name == "EndDeviceListLink":
        return await end_device.select_aggregator_site_count(
            session=session, aggregator_id=aggregator_id, after=datetime.min
        )
    elif list_link_name == "MirrorUsagePointListLink":
        return await site_reading.count_site_reading_types_for_aggregator(
            session=session, aggregator_id=aggregator_id, changed_after=datetime.min
        )
    else:
        raise NotImplementedError(f"No resource count implemented for '{list_link_name}'")


def add_resource_counts_to_links(
    links: dict[str, dict[str, str]], resource_counts: dict[str, int]
) -> dict[str, dict[str, str]]:
    """Adds the resource counts to the links under the "all_" key.

    Example:
        if links = {"CustomerAccountListLink": {"href": "/bill"}} and resource_counts={"CustomerAccountListLink": "5"}
        return {"CustomerAccountListLink": {"href": "/bill", "all_"="5"}}

    Args:
        links: dictionary containing the links and their parameters to be updated (typically only href)
        resource_counts: dictionary mapping links to their resource counts.

    Returns:
        Updated links dictionary with the resource counts added.
    """
    for link_name, link_parameters in links.items():
        if link_name in resource_counts:
            link_parameters["all_"] = str(resource_counts[link_name])
    return links


def check_link_supported(
    link_name: str,
    link_map: dict[str, LinkParameters] = SEP2_LINK_MAP,
) -> bool:
    """Checks if a link is supported by the server

    Links and ListLinks belong to function-sets. If a function set is supported then the corresponding Link or ListLink
    must also be supported.

    Args:
        link_name: The name of the link as string e.g. "EndDeviceListLink" or "TimeLink".
        link_map: The mapping from links to their function set. Defaults to SEP2_LINK_MAP.

    Return:
        True if the link is part of a function set that is fully supported.

    Raises:
        ValueError: If `link_name` isn't recognized.
    """
    if link_name not in link_map:
        raise ValueError(f"Unknown Link or ListLink: {link_name}")

    # Determine which function-set the link is part of
    function_set = link_map[link_name].function_set

    # Check whether function-set is supported by the server
    return check_function_set_supported(function_set)


def check_function_set_supported(function_set: FunctionSet, function_set_status: dict = FUNCTION_SET_STATUS) -> bool:
    """Checks whether a function-set is fully supported.

    Args:
        function_set: A FunctionSet
        function_set_status: Mapping between function-set and function-set statuses. Defaults to FUNCTION_SET_STATUS.

    Returns:
        True if the function set is fully supported else False for partial or no support.

    Raises:
        ValueError for unknown function-sets (missing from function_set_status)
    """
    if function_set not in function_set_status:
        raise ValueError(f"Unknown function set '{function_set}'")

    return function_set_status[function_set] == FunctionSetStatus.SUPPORTED


def get_formatted_links(
    link_names: Iterable[str],
    rs_params: RequestStateParameters,
    uri_parameters: Optional[dict] = None,
    link_map: dict[str, LinkParameters] = SEP2_LINK_MAP,
) -> dict[str, dict[str, str]]:
    """
    Determines complete link URIs (formatted with the user-supplied parameters)

    Example:
        If link_names = ["EndDeviceLink"] and uri_parameters = {"site_id" = 5}
        returns the mapping {"EndDeviceLink": {"href": "/edev/5"}}

    Args:
        link_names: A list of link-names.
        rs_params: Request state parameters that might influence the links being generated
        uri_parameters: The parameters to be inserted into the link URI
        link_map: Maps link-names to URIs. Defaults to using SEP2_LINK_MAP.

    Returns:
        A mapping from the link-name to the link's complete URI.

    Raises:
        MissingUriParameterError: when URI parameters are required by the URI but are not supplied.
    """
    if uri_parameters is None:
        uri_parameters = {}

    links = {}
    for link_name in link_names:
        if link_name in link_map:
            uri = link_map[link_name].uri
            try:
                formatted_uri = generate_href(uri, rs_params, **uri_parameters)
            except KeyError as ex:
                raise MissingUriParameterError(f"KeyError for params {uri_parameters} error {ex}.")
            links[link_name] = {"href": formatted_uri}
    return links


def get_link_field_names(schema: dict) -> list[str]:
    """
    Inspect the pydantic schema and return all the field names for fields derived from 'Link' or 'ListLink'.

    For an example model,

        class MyModel(Resource):
            MySomethingElse: Optional[SomethingElse] = element()
            MyLink: Link = element()
            MyOptionalLink: Optional[Link] = element()
            MyListLink: ListLink = element()

    Calling `get_link_field_names(MyModel.schema())`
    will return ["MyLink", "MyOptionalLink", "MyListLink"]

    Args:
        pydantic schema

    Returns:
        List of 'LinkLink' and 'Link' field names as strings.
    """
    try:
        properties = schema["properties"]
    except KeyError:
        raise ValueError("'schema' not a valid pydantic schema")

    result = []
    for k, v in properties.items():
        if "$ref" in v and v["$ref"] in ["#/definitions/Link", "#/definitions/ListLink"]:
            result.append(k)
    return result
