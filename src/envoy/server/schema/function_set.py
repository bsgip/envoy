from enum import Enum, auto


class FunctionSet(Enum):
    Unknown = auto()
    DeviceCapability = auto()
    SelfDeviceResource = auto()
    EndDeviceResource = auto()
    FunctionSetAssignments = auto()
    SubscriptionAndNotification = auto()
    Response = auto()
    Time = auto()
    DeviceInformation = auto()
    PowerStatus = auto()
    NetworkStatus = auto()
    LogEvent = auto()
    ConfigurationResource = auto()
    SoftwareDownload = auto()
    DemandResponseAndLoadControl = auto()
    Metering = auto()
    Pricing = auto()
    Messaging = auto()
    Billing = auto()
    Prepayment = auto()
    FlowReservation = auto()
    DistributedEnergyResources = auto()
    # According to section 10.11 Metering Mirror is its own function set...
    # but according to Annex A the Metering Mirror endpoints are part of the Metering function set.
    # This list was created from Annex A so doesn't include MeteringMirror as it's own function set.
    MeteringMirror = auto()


# Should this be called FunctionSetSupportLevel instead?
# Could FunctionSetStatus be used to control function-set enabled/disabled? Would we ever want this?
class FunctionSetStatus(Enum):
    UNSUPPORTED = auto()
    PARTIAL_SUPPORT = auto()
    SUPPORTED = auto()


FUNCTION_SET_STATUS = {
    FunctionSet.Unknown: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.DeviceCapability: FunctionSetStatus.SUPPORTED,
    FunctionSet.SelfDeviceResource: FunctionSetStatus.SUPPORTED,
    FunctionSet.EndDeviceResource: FunctionSetStatus.SUPPORTED,
    FunctionSet.FunctionSetAssignments: FunctionSetStatus.SUPPORTED,
    FunctionSet.SubscriptionAndNotification: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.Response: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.Time: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.DeviceInformation: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.PowerStatus: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.NetworkStatus: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.LogEvent: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.ConfigurationResource: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.SoftwareDownload: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.DemandResponseAndLoadControl: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.Metering: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.MeteringMirror: FunctionSetStatus.SUPPORTED,
    FunctionSet.Pricing: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.Messaging: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.Billing: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.Prepayment: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.FlowReservation: FunctionSetStatus.UNSUPPORTED,
    FunctionSet.DistributedEnergyResources: FunctionSetStatus.UNSUPPORTED,
}
