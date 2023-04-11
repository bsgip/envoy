import sys

from envoy.server.schema.sep2.base import Link, ListLink

# The following Resources do not have associated Link objects:
# A.2.4.2, A.2.5.2, A.2.5.4, A.2.6.2, A.2.6.4-A.2.6.9, A.3.2.3, A.3.4.2, A.3.4.4,
# A.3.4.6, A.3.4.8, A.3.4.10, A.3.4.12, A.3.5.2, A.4.1.3, A.4.3.5, A.4.3.7, A.4.4.7,
# A.4.4.11, A.4.5.7, A.4.5.8, A.4.5.9, A.4.6.2, A.4.6.5, A.4.7.4, A.4.7.7, A.4.7.9,
# A.4.7.11, A.4.7.13, A.4.7.15, A.4.7.17, A.4.8.7, A.4.8.9, A.4.9.2, A.4.9.4, A.4.10.5,
# A.4.10.14
_link_classes = [
    # ("AccountBalanceLink", "/ppy/{id1}/ab"),
    # ("AssociatedUsagePointLink", "/edev/{site_id}/der/{id2}/upt"),
    # ("ConfigurationLink", "/edev/{site_id}/cfg"),
    # ("CustomerAccountLink", "/bill/{id1}"),
    # ("DemandResponseProgramLink", "/dr/{id1}"),
    # ("DERAvailabilityLink", "/edev/{site_id}/der/{id2}/dera"),
    # ("DERCapabilityLink", "/edev/{site_id}/der/{id2}/dercap"),
    # ("DefaultDERControlLink", "/derp/{id1}/dderc"),
    # ("DERCurveLink", "/derp/{id1}/dc/{id2}"),
    # ("DERLink", "/edev/{site_id}/der/{id2}"),
    # ("DERProgramLink", "/derp/{id1}"),
    # ("DERSettingsLink", "/edev/{site_id}/der/{id2}/derg"),
    # ("DERStatusLink", "/edev/{site_id}/der/{id2}/ders"),
    # ("DeviceCapabilityLink", "/dcap"),
    # ("DeviceInformationLink", "/edev/{site_id}/di"),
    # ("DeviceStatusLink", "/edev/{site_id}/dstat"),
    ("EndDeviceLink", "/edev/{site_id}"),
    # ("FileLink", "/file/{id1}"),
    # ("FileStatusLink", "/edev/{site_id}/fs"),
    # ("MeterReadingLink", "/upt/{id1}/mr/{id2}"),
    # ("PowerStatusLink", "/edev/{site_id}/ps"),
    # ("PrepaymentLink", "/ppy/{id1}"),
    # ("PrepayOperationStatusLink", "/ppy/{id1}/os"),
    # ("RateComponentLink", "/tp/{id1}/rc/{id2}"),
    # ("ReadingLink", "/upt/{id1}/mr/{id2}/rs/{id3}/r/{id4}"),
    # ("ReadingTypeLink", "/upt/{id1}/mr/{id2}/rt"),
    # ("RegistrationLink", "/edev/{site_id}/rg"),
    # ("SelfDeviceLink", "/sdev"),
    # ("ServiceSupplierLink", "/bill/{id1}/ss"),
    # ("TariffProfileLink", "/tp/{id1}"),
    # ("TimeLink", "/tm"),
    # ("UsagePointLink", "/upt/{id1}"),
]


_list_link_classes = [
    # ("ActiveBillingPeriodListLink", "/bill/{id1}/ca/{id2}/actbp"),
    # ("ActiveCreditRegisterListLink", ""),  # There is NO ActiveFlowReservationList in Sep2!!
    # ("ActiveDERControlListLink", "/derp/{id1}/actderc"),
    # ("ActiveEndDeviceControlListLink", "/dr/{id1}/actedc"),
    # ("ActiveFlowReservationListLink", ""),  # There is NO ActiveFlowReservationList in Sep2!!
    # ("ActiveProjectionReadingListLink", ""),  # There is NO ActiveProjectionReadingList in Sep2!!
    # ("ActiveSupplyInterruptionOverrideListLink", "/ppy/{id1}/actsi"),
    # ("ActiveTargetReadingListLink", ""),  # There is NO ActiveTargeReadingList in Sep2!!
    # ("ActiveTextMessageListLink", "/msg/{id1}/acttxt"),
    # ("ActiveTimeTariffIntervalListLink", "/tp/{id1}/rc/{id2}/acttti"),
    # ("AssociatedDERProgramListLink", "/edev/{site_id}/der/{id2}/derp"),
    # ("BillingPeriodListLink", "/bill/{id1}/ca/{id2}/bp"),
    # ("BillingReadingListLink", "/brs/{id1}/br"),
    # ("BillingReadingSetListLink", "/brs"),
    # ("ConsumptionTariffIntervalListLink", "/tp/{id1}/rc/{id2}/tti/{id3}/cti"),
    # ("CreditRegisterListLink", "/ppy/{id1}/cr"),
    # ("CustomerAccountListLink", "/bill"),
    # ("CustomerAgreementListLink", "/bill/{id1}/ca"),
    # ("DemandResponseProgramListLink", "/dr"),  # /drp used in Step 11 p275 of Sep2
    # ("DERControlListLink", "/derp/{id1}/derc"),
    # ("DERCurveListLink", "/derp/{id1}/dc"),
    # ("DERListLink", "/edev/{site_id}/der"),
    # ("DERProgramListLink", "/derp"),
    # ("EndDeviceControlListLink", "/dr/{id1}/edc"),
    ("EndDeviceListLink", "/edev"),
    # ("FileListLink", "/file"),
    # ("FlowReservationRequestListLink", "/edev/{site_id}/frq"),
    # ("FlowReservationResponseListLink", "/edev/{site_id}/frp"),
    # ("FunctionSetAssignmentsListLink", "/edev/{site_id}/fsa"),
    # ("HistoricalReadingListLink", "/bill/{id1}/ca/{id2}/ver"),
    # ("IPAddrListLink", "/edev/{site_id}/ns/{id2}/addr"),
    # ("IPInterfaceListLink", "/edev/{site_id}/ns"),
    # ("LLInterfaceListLink", "/edev/{site_id}/ns/{id2}/ll"),
    # ("LoadShedAvailabilityListLink", "/edev/{site_id}/lsl"),
    # ("LogEventListLink", "/edev/{site_id}/lel"),
    # ("MessagingProgramListLink", "/msg"),
    # ("MeterReadingListLink", "/upt/{id1}/mr"),
    # ("MirrorUsagePointListLink", "/mup"),
    # ("NeighborListLink", "/edev/{site_id}/ns/{id2}/ll/{id3}/nbh"),
    # ("NotificationListLink", "/ntfy"),
    # ("PrepaymentListLink", "/ppy"),
    # ("PriceResponseCfgListLink", "/edev/{site_id}/cfg/prcfg"),
    # ("ProjectionReadingListLink", "/bill/{id1}/ca/{id2}/pro"),
    # ("RateComponentListLink", "/tp/{id1}/rc"),
    # ("ReadingListLink", "/upt/{id1}/mr/{id2}/rs/{id3}/r"),
    # ("ReadingSetListLink", "/upt/{id1}/mr/{id2}/rs"),
    # ("ResponseListLink", "/rsps/{id1}/rsp"),
    # ("ResponseSetListLink", "/rsps"),
    # ("RPLInstanceListLink", "/edev/{site_id}/ns/{id2}/addr/{id3}/rpl"),
    # ("RPLSourceRoutesListLink", "/edev/{site_id}/ns/{id2}/addr/{id3}/rpl/{id4}/srt"),
    # ("SubscriptionListLink", "/edev/{site_id}/sub"),
    # ("SupplyInterruptionOverrideListLink", "/ppy/{id1}/si"),
    # ("SupportedLocaleListLink", "/edev/{site_id}/di/loc"),
    # ("TargetReadingListLink", "/bill/{id1}/ca/{id2}/tar"),
    # ("TariffProfileListLink", "/tp"),
    # ("TextMessageListLink", "/msg/{id1}/txt"),
    # ("TimeTariffIntervalListLink", "/tp/{id1}/rc/{id2}/tti"),
    # ("UsagePointListLink", "/upt"),
]


_current_module = sys.modules[__name__]

# Create classes for all the Link types
for _link_class in _link_classes:
    _class_name, _href = _link_class
    setattr(_current_module, _class_name, type(_class_name, (Link,), {"href": _href}))

# Create classes for all the ListLink types
for _list_link_class in _list_link_classes:
    _class_name, _href = _list_link_class
    setattr(_current_module, _class_name, type(_class_name, (ListLink,), {"href": _href}))
