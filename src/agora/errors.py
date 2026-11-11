class TransientError(Exception):
    """A failure that may go away if retried, such as a timeout or a 5xx response."""


class PermanentError(Exception):
    """A failure that will repeat if retried, such as an invalid API key."""
