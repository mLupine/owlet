class OwletError(Exception):
    """Generic exception."""


class OwletConnectionError(OwletError):
    """When a connection error occurs, or the cloud answered with a server error.

    Transient: the caller should retry later, never ask for the login again.
    """


class OwletRateLimitError(OwletConnectionError):
    """When the Owlet cloud or the login service rate limited the request.

    retry_after is the number of seconds the service asked us to wait, when
    it said so.
    """

    def __init__(self, message: str = "", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class OwletAuthenticationError(OwletError):
    """When login details are incorrect."""


class OwletCredentialsError(OwletError):
    """When login creds are incorrect, api no longer returns if this is username or password that is incorrect."""


class OwletDevicesError(OwletError):
    """when no devices are found."""


class OwletReadOnlyError(OwletError):
    """When code tries to write a property other than the allowed ones (APP_ACTIVE)."""


class OwletEmailError(OwletCredentialsError):
    """When the email address is unknown or invalid.

    Accounts with email enumeration protection only return
    OwletCredentialsError, so callers should also handle the base class.
    """


class OwletPasswordError(OwletCredentialsError):
    """When the password is incorrect.

    Accounts with email enumeration protection only return
    OwletCredentialsError, so callers should also handle the base class.
    """
