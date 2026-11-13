"""AGORA's own exceptions, one per kind of failure."""


class TransientError(Exception):
    """A temporary failure, such as a timeout, that may succeed if retried."""


class PermanentError(Exception):
    """A failure that retrying won't fix, such as an invalid API key."""


class SchemaValidationError(Exception):
    """The agent ran out of attempts without producing a valid output."""


class AuditRejected(Exception):
    """The auditor rejected the artifact."""


class InvalidTransition(Exception):
    """A task tried to move to a state not allowed from its current one."""
