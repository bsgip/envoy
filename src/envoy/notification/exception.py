from datetime import datetime
from typing import Optional


class NotificationError(Exception):
    """Base type for all deliberately raised errors in the NotificationServer"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class NotificationTransmitError(NotificationError):
    """Exception raised during transmission - logs rudimentary metadata about the transmission"""

    transmit_start: datetime
    transmit_end: datetime
    http_status_code: Optional[int]

    def __init__(
        self,
        message: str,
        transmit_start: datetime,
        transmit_end: datetime,
        http_status_code: Optional[int],
        *args: object,
    ) -> None:
        self.transmit_start = transmit_start
        self.transmit_end = transmit_end
        self.http_status_code = http_status_code
        super().__init__(message, *args)
