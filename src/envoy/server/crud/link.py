import logging
from datetime import datetime

import pydantic_xml
from fastapi_async_sqlalchemy import db

from envoy.server.crud import end_device
from envoy.server.schema import uri
from envoy.server.schema.function_set import FUNCTION_SET_STATUS, FunctionSet, FunctionSetStatus

logger = logging.getLogger(__name__)


class MissingUriParameterError(Exception):
    pass


SEP2_LINK_MAP = {
    "AccountBalanceLink": {
        "uri": uri.AccountBalanceUri,
        "function-set": FunctionSet.Prepayment,
    },
    "ActiveBillingPeriodListLink": {
        "uri": uri.ActiveBillingPeriodListUri,
        "function-set": FunctionSet.Billing,
    },
    "ActiveCreditRegisterListLink": {  # There is NO ActiveFlowReservationList in Sep2!!
        "uri": uri.ActiveCreditRegisterListUri,
        "function-set": FunctionSet.Unknown,
    },
    "ActiveDERControlListLink": {
        "uri": uri.ActiveDERControlListUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "ActiveEndDeviceControlListLink": {
        "uri": uri.ActiveEndDeviceControlListUri,
        "function-set": FunctionSet.DemandResponseAndLoadControl,
    },
    "ActiveFlowReservationListLink": {  # There is NO ActiveFlowReservationList in Sep2!!
        "uri": uri.ActiveFlowReservationListUri,
        "function-set": FunctionSet.Unknown,
    },
    "ActiveProjectionReadingListLink": {  # There is NO ActiveProjectionReadingList in Sep2!!
        "uri": uri.ActiveProjectionReadingListUri,
        "function-set": FunctionSet.Unknown,
    },
    "ActiveSupplyInterruptionOverrideListLink": {
        "uri": uri.ActiveSupplyInterruptionOverrideListUri,
        "function-set": FunctionSet.Prepayment,
    },
    "ActiveTargetReadingListLink": {  # There is NO ActiveTargeReadingList in Sep2!!
        "uri": uri.ActiveTargetReadingListUri,
        "function-set": FunctionSet.Unknown,
    },
    "ActiveTextMessageListLink": {
        "uri": uri.ActiveTextMessageListUri,
        "function-set": FunctionSet.Messaging,
    },
    "ActiveTimeTariffIntervalListLink": {
        "uri": uri.ActiveTimeTariffIntervalListUri,
        "function-set": FunctionSet.Pricing,
    },
    "AssociatedDERProgramListLink": {
        "uri": uri.AssociatedDERProgramListUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "AssociatedUsagePointLink": {
        "uri": uri.AssociatedUsagePointUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "BillingPeriodListLink": {
        "uri": uri.BillingPeriodListUri,
        "function-set": FunctionSet.Billing,
    },
    "BillingReadingListLink": {
        "uri": uri.BillingReadingListUri,
        "function-set": FunctionSet.Billing,
    },
    "BillingReadingSetListLink": {
        "uri": uri.BillingReadingSetListUri,
        "function-set": FunctionSet.Billing,
    },
    "ConfigurationLink": {
        "uri": uri.ConfigurationUri,
        "function-set": FunctionSet.ConfigurationResource,
    },
    "ConsumptionTariffIntervalListLink": {
        "uri": uri.ConsumptionTariffIntervalListUri,
        "function-set": FunctionSet.Pricing,
    },
    "CreditRegisterListLink": {
        "uri": uri.CreditRegisterListUri,
        "function-set": FunctionSet.Prepayment,
    },
    "CustomerAccountListLink": {
        "uri": uri.CustomerAccountListUri,
        "function-set": FunctionSet.Billing,
    },
    "CustomerAccountLink": {
        "uri": uri.CustomerAccountUri,
        "function-set": FunctionSet.Billing,
    },
    "CustomerAgreementListLink": {
        "uri": uri.CustomerAgreementListUri,
        "function-set": FunctionSet.Billing,
    },
    "DefaultDERControlLink": {
        "uri": uri.DefaultDERControlUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DemandResponseProgramListLink": {
        "uri": uri.DemandResponseProgramListUri,
        "function-set": FunctionSet.DemandResponseAndLoadControl,
    },
    "DemandResponseProgramLink": {
        "uri": uri.DemandResponseProgramUri,
        "function-set": FunctionSet.DemandResponseAndLoadControl,
    },
    "DERAvailabilityLink": {
        "uri": uri.DERAvailabilityUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERCapabilityLink": {
        "uri": uri.DERCapabilityUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERControlListLink": {
        "uri": uri.DERControlListUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERCurveListLink": {
        "uri": uri.DERCurveListUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERCurveLink": {
        "uri": uri.DERCurveUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERListLink": {
        "uri": uri.DERListUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERProgramListLink": {
        "uri": uri.DERProgramListUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERProgramLink": {
        "uri": uri.DERProgramUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERSettingsLink": {
        "uri": uri.DERSettingsUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERStatusLink": {
        "uri": uri.DERStatusUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DERLink": {
        "uri": uri.DERUri,
        "function-set": FunctionSet.DistributedEnergyResources,
    },
    "DeviceCapabilityLink": {
        "uri": uri.DeviceCapabilityUri,
        "function-set": FunctionSet.DeviceCapability,
    },
    "DeviceInformationLink": {
        "uri": uri.DeviceInformationUri,
        "function-set": FunctionSet.DeviceInformation,
    },
    "DeviceStatusLink": {
        "uri": uri.DeviceStatusUri,
        "function-set": FunctionSet.EndDeviceResource,
    },
    "EndDeviceControlListLink": {
        "uri": uri.EndDeviceControlListUri,
        "function-set": FunctionSet.DemandResponseAndLoadControl,
    },
    "EndDeviceListLink": {
        "uri": uri.EndDeviceListUri,
        "function-set": FunctionSet.EndDeviceResource,
    },
    "EndDeviceLink": {
        "uri": uri.EndDeviceUri,
        "function-set": FunctionSet.EndDeviceResource,
    },
    "FileListLink": {
        "uri": uri.FileListUri,
        "function-set": FunctionSet.SoftwareDownload,
    },
    "FileStatusLink": {
        "uri": uri.FileStatusUri,
        "function-set": FunctionSet.SoftwareDownload,
    },
    "FileLink": {
        "uri": uri.FileUri,
        "function-set": FunctionSet.SoftwareDownload,
    },
    "FlowReservationRequestListLink": {
        "uri": uri.FlowReservationRequestListUri,
        "function-set": FunctionSet.FlowReservation,
    },
    "FlowReservationResponseListLink": {
        "uri": uri.FlowReservationResponseListUri,
        "function-set": FunctionSet.FlowReservation,
    },
    "FunctionSetAssignmentsListLink": {
        "uri": uri.FunctionSetAssignmentsListUri,
        "function-set": FunctionSet.FunctionSetAssignments,
    },
    "HistoricalReadingListLink": {
        "uri": uri.HistoricalReadingListUri,
        "function-set": FunctionSet.Billing,
    },
    "IPAddrListLink": {
        "uri": uri.IPAddrListUri,
        "function-set": FunctionSet.NetworkStatus,
    },
    "IPInterfaceListLink": {
        "uri": uri.IPInterfaceListUri,
        "function-set": FunctionSet.NetworkStatus,
    },
    "LLInterfaceListLink": {
        "uri": uri.LLInterfaceListUri,
        "function-set": FunctionSet.NetworkStatus,
    },
    "LoadShedAvailabilityListLink": {
        "uri": uri.LoadShedAvailabilityListUri,
        "function-set": FunctionSet.DemandResponseAndLoadControl,
    },
    "LogEventListLink": {
        "uri": uri.LogEventListUri,
        "function-set": FunctionSet.LogEvent,
    },
    "MessagingProgramListLink": {
        "uri": uri.MessagingProgramListUri,
        "function-set": FunctionSet.Messaging,
    },
    "MeterReadingListLink": {
        "uri": uri.MeterReadingListUri,
        "function-set": FunctionSet.Metering,
    },
    "MeterReadingLink": {
        "uri": uri.MeterReadingUri,
        "function-set": FunctionSet.Metering,
    },
    "MirrorUsagePointListLink": {
        "uri": uri.MirrorUsagePointListUri,
        "function-set": FunctionSet.Metering,
    },
    "NeighborListLink": {
        "uri": uri.NeighborListUri,
        "function-set": FunctionSet.NetworkStatus,
    },
    "NotificationListLink": {
        "uri": uri.NotificationListUri,
        "function-set": FunctionSet.SubscriptionAndNotification,
    },
    "PowerStatusLink": {
        "uri": uri.PowerStatusUri,
        "function-set": FunctionSet.PowerStatus,
    },
    "PrepaymentListLink": {
        "uri": uri.PrepaymentListUri,
        "function-set": FunctionSet.Prepayment,
    },
    "PrepaymentLink": {
        "uri": uri.PrepaymentUri,
        "function-set": FunctionSet.Prepayment,
    },
    "PrepayOperationStatusLink": {
        "uri": uri.PrepayOperationStatusUri,
        "function-set": FunctionSet.Prepayment,
    },
    "PriceResponseCfgListLink": {
        "uri": uri.PriceResponseCfgListUri,
        "function-set": FunctionSet.ConfigurationResource,
    },
    "ProjectionReadingListLink": {
        "uri": uri.ProjectionReadingListUri,
        "function-set": FunctionSet.Billing,
    },
    "RateComponentListLink": {
        "uri": uri.RateComponentListUri,
        "function-set": FunctionSet.Pricing,
    },
    "RateComponentLink": {
        "uri": uri.RateComponentUri,
        "function-set": FunctionSet.Pricing,
    },
    "ReadingListLink": {
        "uri": uri.ReadingListUri,
        "function-set": FunctionSet.Metering,
    },
    "ReadingSetListLink": {
        "uri": uri.ReadingSetListUri,
        "function-set": FunctionSet.Metering,
    },
    "ReadingTypeLink": {
        "uri": uri.ReadingTypeUri,
        "function-set": FunctionSet.Metering,
    },
    "ReadingLink": {
        "uri": uri.ReadingUri,
        "function-set": FunctionSet.Metering,
    },
    "RegistrationLink": {
        "uri": uri.RegistrationUri,
        "function-set": FunctionSet.EndDeviceResource,
    },
    "ResponseListLink": {
        "uri": uri.ResponseListUri,
        "function-set": FunctionSet.Response,
    },
    "ResponseSetListLink": {
        "uri": uri.ResponseSetListUri,
        "function-set": FunctionSet.Response,
    },
    "RPLInstanceListLink": {
        "uri": uri.RPLInstanceListUri,
        "function-set": FunctionSet.NetworkStatus,
    },
    "RPLSourceRoutesListLink": {
        "uri": uri.RPLSourceRoutesListUri,
        "function-set": FunctionSet.NetworkStatus,
    },
    "SelfDeviceLink": {
        "uri": uri.SelfDeviceUri,
        "function-set": FunctionSet.SelfDeviceResource,
    },
    "ServiceSupplierLink": {
        "uri": uri.ServiceSupplierUri,
        "function-set": FunctionSet.Billing,
    },
    "SubscriptionListLink": {
        "uri": uri.SubscriptionListUri,
        "function-set": FunctionSet.SubscriptionAndNotification,
    },
    "SupplyInterruptionOverrideListLink": {
        "uri": uri.SupplyInterruptionOverrideListUri,
        "function-set": FunctionSet.Prepayment,
    },
    "SupportedLocaleListLink": {
        "uri": uri.SupportedLocaleListUri,
        "function-set": FunctionSet.DeviceInformation,
    },
    "TargetReadingListLink": {
        "uri": uri.TargetReadingListUri,
        "function-set": FunctionSet.Billing,
    },
    "TariffProfileListLink": {
        "uri": uri.TariffProfileListUri,
        "function-set": FunctionSet.Pricing,
    },
    "TariffProfileLink": {
        "uri": uri.TariffProfileUri,
        "function-set": FunctionSet.Pricing,
    },
    "TextMessageListLink": {
        "uri": uri.TextMessageListUri,
        "function-set": FunctionSet.Messaging,
    },
    "TimeTariffIntervalListLink": {
        "uri": uri.TimeTariffIntervalListUri,
        "function-set": FunctionSet.Pricing,
    },
    "TimeLink": {
        "uri": uri.TimeUri,
        "function-set": FunctionSet.Time,
    },
    "UsagePointListLink": {
        "uri": uri.UsagePointListUri,
        "function-set": FunctionSet.Metering,
    },
    "UsagePointLink": {
        "uri": uri.UsagePointUri,
        "function-set": FunctionSet.Metering,
    },
}


async def get_supported_links(
    model: pydantic_xml.BaseXmlModel, aggregator_id: int, uri_parameters: dict = None
) -> dict:
    link_names = get_link_field_names(model.schema())
    supported_links_names = filter(check_link_supported, link_names)
    supported_links = get_formatted_links(supported_links_names, uri_parameters)
    resource_counts = await get_resource_counts(supported_links.keys(), aggregator_id)
    add_resource_counts_to_list_links(supported_links, resource_counts)

    return supported_links


async def get_resource_counts(link_names: list[str], aggregator_id: int) -> dict:
    resource_counts = {}
    for link_name in link_names:
        if link_name.endswith("ListLink"):
            try:
                count = await get_resource_count(link_name, aggregator_id)
                resource_counts[link_name] = str(count)
            except NotImplementedError as e:
                logger.debug(e)
    return resource_counts


async def get_resource_count(link_name: str, aggregator_id: int) -> int:
    if link_name == "EndDeviceListLink":
        count = await end_device.select_aggregator_site_count(db.session, aggregator_id, after=datetime.min)
        return count
    else:
        raise NotImplementedError(f"No resource count implemented for '{link_name}'")


def add_resource_counts_to_list_links(links: dict, resource_counts: dict):
    for link_name, link_parameters in links.items():
        if link_name in resource_counts:
            link_parameters["all_"] = resource_counts[link_name]
    return links


def check_link_supported(
    link_name: str,
    link_map: dict = SEP2_LINK_MAP,
):
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
    try:
        # Determine which function-set the link is part of
        function_set = link_map[link_name]["function-set"]
    except KeyError:
        raise ValueError(f"Malformed link mapping {link_map}")

    # Check whether function-set is supported by the server
    return check_function_set_supported(function_set)


def check_function_set_supported(function_set: FunctionSet, function_set_status: list = FUNCTION_SET_STATUS) -> bool:
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


def get_formatted_links(link_names: list, uri_parameters: dict = None, link_map: dict = SEP2_LINK_MAP) -> dict:
    """
    Determines complete link URIs (formatted with the user-supplied parameters)

    Example:
        If link_names = ["EndDeviceLink"] and uri_parameters = {"site_id" = 5}
        returns the mapping {"EndDeviceLink": {"href": "/edev/5"}}

    Args:
        link_names: A list of link-names.
        uri_parameters: The parameters to be inserted into the link URI
        link_map: Maps link-names to URIs. Defaults to using SEP2_LINK_MAP.

    Returns:
        A mapping from the link-name to the link's complete URI.

    Raises:
        MissingUriParameterError: when URI parameters are required by the URI but are not supplied.
    """

    class FailMissingParam(dict):
        def __missing__(self, key):
            raise MissingUriParameterError(f"{key} not found.")

    links = {}
    for link_name in link_names:
        if link_name in link_map:
            links[link_name] = {"href": link_map[link_name]["uri"].format_map(FailMissingParam(uri_parameters))}
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
