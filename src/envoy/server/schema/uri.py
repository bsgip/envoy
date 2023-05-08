# Defines all the URIs
# Some URIs have named parameters e.g. EndDeviceUri = "/edev/{site_id}". These are intended to be filled in with an
# appropriate format statement, for example, EndDeviceUri.format(site_id=4) or EndDeviceUri
# Note: 'id1', 'id2', 'id3' are placeholders and should be replaced with suitable names matching their purpose.

# CSIP-Aus URIs
ConnectionPointUri = "/edev/{site_id}/cp"

# Sep2 URIs
AccountBalanceUri = "/ppy/{id1}/ab"
ActiveBillingPeriodListUri = "/bill/{id1}/ca/{id2}/actbp"
ActiveCreditRegisterListUri = ""  # noqa: E501. There is NO ActiveCreditRegisterList resource in Sep2 despite an ActiveCreditRegisterListLink being defined.
ActiveDERControlListUri = "/derp/{id1}/actderc"
ActiveEndDeviceControlListUri = "/dr/{id1}/actedc"
ActiveFlowReservationListUri = ""  # noqa: E501. There is NO ActiveFlowReservationList resource in Sep2 despite an ActiveFlowReservationListLink being defined.
ActiveProjectionReadingListUri = ""  # noqa: E501. There is NO ActiveProjectionReadingList in resource Sep2 despite an ActiveProjectionReadingListLink being defined.
ActiveSupplyInterruptionOverrideListUri = "/ppy/{id1}/actsi"
ActiveTargetReadingListUri = ""  # noqa: E501. There is NO ActiveTargetReadingList resource in Sep2 despite an ActiveTargetReadingListLink being defined.
ActiveTextMessageListUri = "/msg/{id1}/acttxt"
ActiveTimeTariffIntervalListUri = "/tp/{id1}/rc/{id2}/acttti"
AssociatedDERProgramListUri = "/edev/{site_id}/der/{id2}/derp"
AssociatedUsagePointUri = "/edev/{site_id}/der/{id2}/upt"
BillingPeriodListUri = "/bill/{id1}/ca/{id2}/bp"
BillingReadingListUri = "/brs/{id1}/br"
BillingReadingSetListUri = "/brs"
ConfigurationUri = "/edev/{site_id}/cfg"
ConsumptionTariffIntervalListUri = (
    "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}/tti/{tti_id}/cti/{sep2_price}"  # noqa e501
)
ConsumptionTariffIntervalUri = (
    "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}/tti/{tti_id}/cti/{sep2_price}/1"  # noqa e501
)
CreditRegisterListUri = "/ppy/{id1}/cr"
CustomerAccountListUri = "/bill"
CustomerAccountUri = "/bill/{id1}"
CustomerAgreementListUri = "/bill/{id1}/ca"
DefaultDERControlUri = "/derp/{id1}/dderc"
DemandResponseProgramListUri = "/dr"  # /drp used in Step 11 p275 of Sep2
DemandResponseProgramUri = "/dr/{id1}"
DERAvailabilityUri = "/edev/{site_id}/der/{id2}/dera"
DERCapabilityUri = "/edev/{site_id}/der/{id2}/dercap"
DERControlListUri = "/derp/{site_id}/{der_program_id}/derc"
DERControlListByDateUri = "/derp/{site_id}/{der_program_id}/derc/{date}"
DERCurveListUri = "/derp/{id1}/dc"
DERCurveUri = "/derp/{id1}/dc/{id2}"
DERListUri = "/edev/{site_id}/der"
# DERProgramListUri = "/derp"
# DERProgramUri = "/derp/{id1}"
# Modify DERProgram URIs to be site-scoped
DERProgramListUri = "/edev/{site_id}/derp"
DERProgramUri = "/edev/{site_id}/derp/{id1}"
DERSettingsUri = "/edev/{site_id}/der/{id2}/derg"
DERStatusUri = "/edev/{site_id}/der/{id2}/ders"
DERUri = "/edev/{site_id}/der/{id2}"
DeviceCapabilityUri = "/dcap"
DeviceInformationUri = "/edev/{site_id}/di"
DeviceStatusUri = "/edev/{site_id}/dstat"
EndDeviceControlListUri = "/dr/{id1}/edc"
EndDeviceListUri = "/edev"
EndDeviceUri = "/edev/{site_id}"
FileListUri = "/file"
FileStatusUri = "/edev/{site_id}/fs"
FileUri = "/file/{id1}"
FlowReservationRequestListUri = "/edev/{site_id}/frq"
FlowReservationResponseListUri = "/edev/{site_id}/frp"
FunctionSetAssignmentsListUri = "/edev/{site_id}/fsa"
FunctionSetAssignmentsUri = "/edev/{site_id}/fsa/{fsa_id}"
HistoricalReadingListUri = "/bill/{id1}/ca/{id2}/ver"
IPAddrListUri = "/edev/{site_id}/ns/{id2}/addr"
IPInterfaceListUri = "/edev/{site_id}/ns"
LLInterfaceListUri = "/edev/{site_id}/ns/{id2}/ll"
LoadShedAvailabilityListUri = "/edev/{site_id}/lsl"
LogEventListUri = "/edev/{site_id}/lel"
MessagingProgramListUri = "/msg"
MeterReadingListUri = "/upt/{id1}/mr"
MeterReadingUri = "/upt/{id1}/mr/{id2}"
MirrorUsagePointListUri = "/mup"
NeighborListUri = "/edev/{site_id}/ns/{id2}/ll/{id3}/nbh"
NotificationListUri = "/ntfy"
PowerStatusUri = "/edev/{site_id}/ps"
PrepaymentListUri = "/ppy"
PrepaymentUri = "/ppy/{id1}"
PrepayOperationStatusUri = "/ppy/{id1}/os"
PriceResponseCfgListUri = "/edev/{site_id}/cfg/prcfg"
PricingReadingTypeUri = "/pricing/rt/{reading_type}"
ProjectionReadingListUri = "/bill/{id1}/ca/{id2}/pro"
RateComponentListUnscopedUri = "/tp/{tariff_id}/rc"
RateComponentListUri = "/tp/{tariff_id}/{site_id}/rc"
RateComponentUri = "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}"
ReadingListUri = "/upt/{id1}/mr/{id2}/rs/{id3}/r"
ReadingSetListUri = "/upt/{id1}/mr/{id2}/rs"
ReadingTypeUri = "/upt/{id1}/mr/{id2}/rt"
ReadingUri = "/upt/{id1}/mr/{id2}/rs/{id3}/r/{id4}"
RegistrationUri = "/edev/{site_id}/rg"
ResponseListUri = "/rsps/{id1}/rsp"
ResponseSetListUri = "/rsps"
RPLInstanceListUri = "/edev/{site_id}/ns/{id2}/addr/{id3}/rpl"
RPLSourceRoutesListUri = "/edev/{site_id}/ns/{id2}/addr/{id3}/rpl/{id4}/srt"
SelfDeviceUri = "/sdev"
ServiceSupplierUri = "/bill/{id1}/ss"
SubscriptionListUri = "/edev/{site_id}/sub"
SupplyInterruptionOverrideListUri = "/ppy/{id1}/si"
SupportedLocaleListUri = "/edev/{site_id}/di/loc"
TargetReadingListUri = "/bill/{id1}/ca/{id2}/tar"
TariffProfileListUnscopedUri = "/tp"
TariffProfileListUri = "/edev/{site_id}/tp"
TariffProfileUnscopedUri = "/tp/{tariff_id}"
TariffProfileUri = "/tp/{tariff_id}/{site_id}"
TextMessageListUri = "/msg/{id1}/txt"
TimeTariffIntervalListUri = "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}/tti"
TimeTariffIntervalUri = "/tp/{tariff_id}/{site_id}/rc/{rate_component_id}/{pricing_reading}/tti/{tti_id}"
TimeUri = "/tm"
UsagePointListUri = "/upt"
UsagePointUri = "/upt/{id1}"
