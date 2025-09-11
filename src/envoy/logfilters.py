import logging


class ExcludeMessageFilter(logging.Filter):
    """Really simple utility for excluding certain logs based on their contents.

    This is intended for deployments that wish to selectively suppress certain log elements via python logging config.

    It will not be loaded by default"""

    def __init__(self, exclude_str: str):
        super().__init__()
        self.exclude_str = exclude_str

    def filter(self, record: logging.LogRecord) -> bool:
        return self.exclude_str not in record.getMessage()
