class SourceAccessDeniedError(Exception):
    """Raised when an external source blocks automated access."""

    def __init__(self, source: str, status_code: int, reason: str) -> None:
        self.source = source
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"{source} access denied with status {status_code}: {reason}")
