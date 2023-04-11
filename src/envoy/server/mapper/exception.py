class InvalidMappingError(Exception):
    """Raised when a mapper cannot map an entity due to an error with the supplied data"""
    message: str

    def __init__(self, message: str) -> None:
        self.message = message
