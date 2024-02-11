class NotificationError(Exception):
    """Base type for all deliberately raised errors in the NotificationServer"""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
